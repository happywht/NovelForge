import asyncio
from typing import AsyncIterator, Dict, Optional, Any, List, Callable
from datetime import datetime
from sqlmodel import Session, select

from app.db.models import Workflow, WorkflowRun
from app.services import nodes as builtin_nodes
from loguru import logger


class LocalAsyncEngine:
    """
    极简本地执行器（MVP）
    - 线性执行 nodes；支持 List.ForEach/List.ForEachRange（body 必须存在）
    - 事件：step_started/step_succeeded/step_failed/run_completed
    - 规范化：执行前对 DSL 做兼容重写（ForEach 无 body → 将紧随节点折叠为 body）
    - 调试支持：支持暂停、恢复、单步执行
    """

    def __init__(self) -> None:
        self._run_tasks: Dict[int, asyncio.Task] = {}
        self._event_queues: Dict[int, "asyncio.Queue[str]"] = {}
        self._paused_runs: Dict[int, asyncio.Event] = {}
        self._debug_runs: set[int] = set()

    # ---------------- background & events ----------------
    async def _publish(self, run_id: int, event: str) -> None:
        # 兜底：若队列不存在则先创建，避免前端晚订阅时丢事件
        queue = self._event_queues.get(run_id)
        if queue is None:
            logger.info(f"[工作流] _publish 发现队列不存在，已兜底创建 run_id={run_id}")
            queue = asyncio.Queue()
            self._event_queues[run_id] = queue
        await queue.put(event)

    async def _close_queue(self, run_id: int) -> None:
        queue = self._event_queues.get(run_id)
        if queue is not None:
            await queue.put("__CLOSE__")

    def _ensure_queue(self, run_id: int) -> asyncio.Queue:
        q = self._event_queues.get(run_id)
        if q is None:
            q = asyncio.Queue()
            self._event_queues[run_id] = q
            logger.info(f"[工作流] 已创建事件队列 run_id={run_id}")
        return q

    def subscribe_events(self, run_id: int) -> AsyncIterator[str]:
        queue = self._ensure_queue(run_id)

        async def _gen() -> AsyncIterator[str]:
            while True:
                item = await queue.get()
                if item == "__CLOSE__":
                    break
                yield item
        return _gen()

    def _background_run(self, coro_factory: Callable[[], asyncio.Future], run_id: int) -> Optional[asyncio.Task]:
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(coro_factory())
        except RuntimeError:
            try:
                import anyio  # type: ignore
                logger.info(f"[工作流] 无事件循环；通过 anyio.from_thread.run 投递 run_id={run_id}")
                return anyio.from_thread.run(asyncio.create_task, coro_factory())
            except Exception:
                logger.warning(f"[工作流] anyio 失败；同步执行 run_id={run_id}")
                asyncio.run(coro_factory())
                return None

    # ---------------- create run ----------------
    def create_run(self, session: Session, workflow: Workflow, scope_json: Optional[dict], params_json: Optional[dict], idempotency_key: Optional[str]) -> WorkflowRun:
        run = WorkflowRun(
            workflow_id=workflow.id,
            definition_version=workflow.version,
            status="queued",
            scope_json=scope_json,
            params_json=params_json,
            idempotency_key=idempotency_key,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        # 提前创建事件队列，确保即便前端稍后订阅也不会丢第一批事件
        self._ensure_queue(run.id)
        logger.info(f"[工作流] Run 已创建并初始化事件队列 run_id={run.id} workflow_id={workflow.id}")
        return run

    # ---------------- debug control ----------------
    def set_debug(self, run_id: int, enabled: bool = True):
        if enabled:
            self._debug_runs.add(run_id)
            if run_id not in self._paused_runs:
                self._paused_runs[run_id] = asyncio.Event()
        else:
            self._debug_runs.discard(run_id)
            if run_id in self._paused_runs:
                self._paused_runs[run_id].set()
                del self._paused_runs[run_id]

    def pause(self, run_id: int):
        if run_id not in self._paused_runs:
            self._paused_runs[run_id] = asyncio.Event()
        else:
            self._paused_runs[run_id].clear()
        logger.info(f"[工作流] 已请求暂停 run_id={run_id}")

    def resume(self, run_id: int):
        if run_id in self._paused_runs:
            self._paused_runs[run_id].set()
            logger.info(f"[工作流] 已请求恢复 run_id={run_id}")

    def step(self, run_id: int):
        if run_id in self._paused_runs:
            self._paused_runs[run_id].set()
            # 立即再次清除，以便执行完当前节点后再次暂停
            # 注意：这需要 _execute_graph 在循环中检查
            logger.info(f"[工作流] 已请求单步执行 run_id={run_id}")

    async def _check_pause(self, run_id: int):
        if run_id in self._paused_runs:
            event = self._paused_runs[run_id]
            if not event.is_set():
                logger.info(f"[工作流] 正在等待恢复 run_id={run_id}...")
                await self._publish(run_id, "event: paused\ndata: waiting for resume\n\n")
                await event.wait()
                if run_id in self._debug_runs:
                    event.clear()  # 调试模式下，单步后继续暂停

    # ---------------- nodes ----------------
    def _resolve_node_fn(self, type_name: str):
        """从节点注册表中获取节点函数"""
        registry = builtin_nodes.get_registered_nodes()
        fn = registry.get(type_name)
        if not fn:
            raise ValueError(f"未知节点类型: {type_name}，已注册的节点: {list(registry.keys())}")
        return fn

    # ---------------- canonicalize ----------------
    @staticmethod
    def _canonicalize(nodes: List[dict]) -> List[dict]:
        """将 DSL 规范化：
        - ForEach/ForEachRange 若无 body，则将后一个节点折叠为其 body，并跳过单独执行。
        """
        out: List[dict] = []
        i = 0
        while i < len(nodes):
            n = nodes[i]
            ntype = n.get("type")
            if ntype in ("List.ForEach", "List.ForEachRange") and not n.get("body") and i + 1 < len(nodes):
                compat = dict(n)
                compat["body"] = [nodes[i + 1]]
                out.append(compat)
                logger.warning("[工作流] 兼容重写：ForEach/Range 缺少 body，已将后一节点折叠为 body")
                i += 2
                continue
            out.append(n)
            i += 1
        return out

    # ---------------- execute ----------------
    async def _execute_dsl(self, session: Session, workflow: Workflow, run: WorkflowRun) -> None:
        dsl: Dict[str, Any] = workflow.definition_json or {}
        raw_nodes: List[dict] = list(dsl.get("nodes") or [])
        
        # 检查是否是标准格式（包含edges）
        is_standard_format = "edges" in dsl and isinstance(dsl["edges"], list)
        
        if is_standard_format:
            # 标准格式：基于edges执行
            await self._execute_standard_format(session, workflow, run, dsl)
        else:
            # 旧格式：保持原有逻辑
            await self._execute_legacy_format(session, workflow, run, raw_nodes)

    async def _execute_standard_format(self, session: Session, workflow: Workflow, run: WorkflowRun, dsl: dict) -> None:
        """执行标准格式的工作流（基于nodes+edges）"""
        nodes: List[dict] = list(dsl.get("nodes") or [])
        edges: List[dict] = list(dsl.get("edges") or [])
        state: Dict[str, Any] = {"scope": run.scope_json or {}, "touched_card_ids": set()}
        
        logger.info(f"[工作流] 开始执行 run_id={run.id} workflow_id={workflow.id} nodes={len(nodes)} edges={len(edges)}")
        
        # 构建执行图
        graph = self._build_execution_graph(nodes, edges)
        
        # 执行工作流
        await self._execute_graph(graph, session, state, run.id)
        
        # 保存结果
        await self._save_execution_result(session, run, state)
    
    def _build_execution_graph(self, nodes: List[dict], edges: List[dict]) -> dict:
        """构建执行图：节点映射、依赖关系、后继关系"""
        node_map = {n["id"]: n for n in nodes}
        dependencies = {}  # node_id -> [predecessor_ids]
        successors = {}    # node_id -> {"body": [...], "next": [...]}
        
        # 构建依赖和后继关系
        for edge in edges:
            source, target = edge["source"], edge["target"]
            handle = edge.get("sourceHandle", "r")
            
            # 记录依赖
            dependencies.setdefault(target, []).append(source)
            
            # 记录后继（区分body和next）
            succ_type = "body" if handle == "b" else "next"
            successors.setdefault(source, {"body": [], "next": []})[succ_type].append(target)
        
        # 找到起始节点
        start_nodes = [n["id"] for n in nodes if n["id"] not in dependencies]
        if not start_nodes and nodes:
            logger.warning("[工作流] 无起始节点，使用第一个节点")
            start_nodes = [nodes[0]["id"]]
        
        return {
            "node_map": node_map,
            "dependencies": dependencies,
            "successors": successors,
            "start_nodes": start_nodes
        }
    
    async def _execute_graph(self, graph: dict, session: Session, state: dict, run_id: int) -> None:
        """执行工作流图"""
        node_map = graph["node_map"]
        dependencies = graph["dependencies"]
        successors = graph["successors"]
        executed = set()
        
        async def execute_node(node_id: str) -> None:
            if node_id in executed or node_id not in node_map:
                return
            
            # 检查暂停状态
            await self._check_pause(run_id)
            
            node = node_map[node_id]
            ntype = node.get("type")
            params = node.get("params") or {}
            
            logger.info(f"[工作流] 执行节点 id={node_id} type={ntype}")
            await self._publish(run_id, f"event: step_started\ndata: {ntype}\n\n")
            
            try:
                # 执行节点
                await self._execute_single_node(node, session, state, run_id, successors.get(node_id, {}), node_map)
                
                # 标记为已执行
                executed.add(node_id)
                
                # 如果是循环节点，标记body节点也已执行
                if ntype in ("List.ForEach", "List.ForEachRange"):
                    executed.update(successors.get(node_id, {}).get("body", []))
                
                logger.info(f"[工作流] 节点成功 id={node_id} type={ntype}")
                await self._publish(run_id, f"event: step_succeeded\ndata: {ntype}\n\n")
                
                # 执行后续节点
                await self._execute_successors(node_id, successors, dependencies, executed, execute_node)
                
            except Exception as e:
                logger.exception(f"[工作流] 节点失败 id={node_id} type={ntype} err={e}")
                await self._publish(run_id, f"event: step_failed\ndata: {ntype}: {e}\n\n")
                raise
        
        # 执行所有起始节点
        for start_id in graph["start_nodes"]:
            await execute_node(start_id)

    async def _execute_successors(self, node_id: str, successors: dict, dependencies: dict, executed: set, execute_node: Callable) -> None:
        """执行后继节点"""
        next_nodes = successors.get(node_id, {}).get("next", [])
        for next_id in next_nodes:
            # 检查所有依赖是否已完成
            deps = dependencies.get(next_id, [])
            if all(d in executed for d in deps):
                await execute_node(next_id)

    async def _execute_single_node(self, node: dict, session: Session, state: dict, run_id: int, 
                                   node_successors: dict, node_map: dict) -> None:
        """执行单个节点"""
        ntype = node.get("type")
        params = node.get("params") or {}
        
        # 循环节点特殊处理
        if ntype in ("List.ForEach", "List.ForEachRange"):
            body_node_ids = node_successors.get("body", [])
            body_nodes = [node_map[bid] for bid in body_node_ids if bid in node_map]
            
            async def body_executor(s, st, p):
                # 循环体执行逻辑
                # 注意：循环体内部也需要支持异步
                await self._execute_body_nodes(body_nodes, s, st, run_id)

            fn = self._resolve_node_fn(ntype)
            # 传入 body_executor 供循环节点调用
            await fn(session, state, params, body_executor=body_executor)
        else:
            # 普通节点
            fn = self._resolve_node_fn(ntype)
            if asyncio.iscoroutinefunction(fn):
                await fn(session, state, params)
            else:
                fn(session, state, params)

    async def _execute_body_nodes(self, body_nodes: List[dict], session, state, run_id: int):
        """执行body节点"""
        for bn in body_nodes:
            # 循环体内节点也检查暂停
            await self._check_pause(run_id)
            
            ntype = bn.get("type")
            params = bn.get("params") or {}
            logger.info(f"[工作流] body节点 type={ntype}")
            try:
                fn = self._resolve_node_fn(ntype)
                if asyncio.iscoroutinefunction(fn):
                    await fn(session, state, params)
                else:
                    fn(session, state, params)
            except Exception as e:  # noqa: BLE001
                logger.exception(f"[工作流] body节点失败 type={ntype} err={e}")
                raise

    async def _execute_legacy_format(self, session: Session, workflow: Workflow, run: WorkflowRun, raw_nodes: List[dict]) -> None:
        """执行旧格式的工作流（线性执行）"""
        nodes = self._canonicalize(raw_nodes)
        state: Dict[str, Any] = {"scope": run.scope_json or {}, "touched_card_ids": set()}
        
        logger.info(f"[工作流] 开始执行(旧格式) run_id={run.id} workflow_id={workflow.id} nodes={len(nodes)}")
        
        for node in nodes:
            # 检查暂停
            await self._check_pause(run_id=run.id)
            
            ntype = node.get("type")
            params = node.get("params") or {}
            
            await self._publish(run.id, f"event: step_started\ndata: {ntype}\n\n")
            try:
                # 旧格式不支持 graph 结构的 successors，传入空
                await self._execute_single_node(node, session, state, run.id, {}, {})
                await self._publish(run.id, f"event: step_succeeded\ndata: {ntype}\n\n")
            except Exception as e:
                logger.exception(f"[工作流] 节点失败 run_id={run.id} type={ntype} err={e}")
                await self._publish(run.id, f"event: step_failed\ndata: {ntype}: {e}\n\n")
                raise

        await self._save_execution_result(session, run, state)

    async def _save_execution_result(self, session: Session, run: WorkflowRun, state: dict) -> None:
        """保存执行结果"""
        run.status = "completed"
        run.finished_at = datetime.now()
        run.result_json = {"touched_card_ids": list(state.get("touched_card_ids", []))}
        session.add(run)
        session.commit()
        
        # 清理调试状态
        self._debug_runs.discard(run.id)
        if run.id in self._paused_runs:
            del self._paused_runs[run.id]
            
        await self._publish(run.id, "event: run_completed\ndata: success\n\n")
        await self._close_queue(run.id)
        logger.info(f"[工作流] Run 已完成 run_id={run.id}")

    # ---------------- public entry ----------------
    def run_workflow_background(self, session: Session, workflow: Workflow, run: WorkflowRun) -> int:
        """后台异步运行工作流"""
        async def _task():
            try:
                # 重新获取 session 避免跨线程问题（如果是在新线程运行）
                # 但在 FastAPI/asyncio 环境下通常直接用传入的
                await self._execute_dsl(session, workflow, run)
            except Exception as e:
                logger.exception(f"[工作流] 运行异常 run_id={run.id} err={e}")
                run.status = "failed"
                run.error_json = {"error": str(e)}
                run.finished_at = datetime.now()
                session.add(run)
                session.commit()
                await self._publish(run.id, f"event: run_failed\ndata: {e}\n\n")
                await self._close_queue(run.id)
            finally:
                if run.id in self._run_tasks:
                    del self._run_tasks[run.id]

        task = self._background_run(_task, run.id)
        if task:
            self._run_tasks[run.id] = task
        return run.id

    def run(self, session: Session, run: WorkflowRun) -> int:
        """兼容旧代码：运行工作流"""
        workflow = session.get(Workflow, run.workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {run.workflow_id}")
        return self.run_workflow_background(session, workflow, run)

    def cancel(self, run_id: int) -> bool:
        """取消正在运行的工作流"""
        task = self._run_tasks.get(run_id)
        if task:
            task.cancel()
            return True
        return False


_engine_instance: Optional[LocalAsyncEngine] = None

def get_engine() -> LocalAsyncEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LocalAsyncEngine()
    return _engine_instance

engine = get_engine()
