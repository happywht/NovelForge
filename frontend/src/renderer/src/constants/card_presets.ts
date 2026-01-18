export interface CardPreset {
    name: string
    description: string
    json_schema: string
    ui_layout: string
    ai_params?: string
}

export const CARD_PRESETS: CardPreset[] = [
    {
        name: '人物卡 (Character)',
        description: '标准人物设定模板，包含基本信息、性格、外貌、背景等。',
        json_schema: JSON.stringify(
            {
                type: 'object',
                properties: {
                    name: { type: 'string', title: '姓名' },
                    age: { type: 'string', title: '年龄' },
                    gender: { type: 'string', title: '性别', enum: ['男', '女', '其他'] },
                    role: { type: 'string', title: '角色定位', enum: ['主角', '配角', '反派', '路人'] },
                    tags: { type: 'array', title: '标签', items: { type: 'string' } },
                    appearance: { type: 'string', title: '外貌描写', format: 'textarea' },
                    personality: { type: 'string', title: '性格特征', format: 'textarea' },
                    background: { type: 'string', title: '背景故事', format: 'textarea' },
                    skills: { type: 'array', title: '技能/能力', items: { type: 'string' } }
                },
                required: ['name', 'role']
            },
            null,
            2
        ),
        ui_layout: JSON.stringify(
            {
                sections: [
                    {
                        title: '基本信息',
                        include: ['name', 'age', 'gender', 'role', 'tags']
                    },
                    {
                        title: '详细设定',
                        include: ['appearance', 'personality', 'skills']
                    },
                    {
                        title: '背景故事',
                        include: ['background']
                    }
                ]
            },
            null,
            2
        )
    },
    {
        name: '地点卡 (Location)',
        description: '用于描述地理位置、场景环境、历史背景。',
        json_schema: JSON.stringify(
            {
                type: 'object',
                properties: {
                    name: { type: 'string', title: '地名' },
                    type: { type: 'string', title: '类型', enum: ['城市', '自然', '建筑', '副本', '其他'] },
                    location: { type: 'string', title: '所属区域' },
                    description: { type: 'string', title: '环境描写', format: 'textarea' },
                    history: { type: 'string', title: '历史背景', format: 'textarea' },
                    atmosphere: { type: 'string', title: '氛围/特色' }
                },
                required: ['name']
            },
            null,
            2
        ),
        ui_layout: JSON.stringify(
            {
                sections: [
                    {
                        title: '基本信息',
                        include: ['name', 'type', 'location', 'atmosphere']
                    },
                    {
                        title: '详细描述',
                        include: ['description', 'history']
                    }
                ]
            },
            null,
            2
        )
    },
    {
        name: '物品卡 (Item)',
        description: '道具、装备、宝物等物品的设定。',
        json_schema: JSON.stringify(
            {
                type: 'object',
                properties: {
                    name: { type: 'string', title: '物品名称' },
                    type: { type: 'string', title: '类别', enum: ['武器', '防具', '消耗品', '关键道具', '其他'] },
                    rarity: { type: 'string', title: '稀有度', enum: ['普通', '稀有', '史诗', '传说'] },
                    function: { type: 'string', title: '功能/用途', format: 'textarea' },
                    description: { type: 'string', title: '外观描述', format: 'textarea' },
                    origin: { type: 'string', title: '来源/出处' }
                },
                required: ['name']
            },
            null,
            2
        ),
        ui_layout: JSON.stringify(
            {
                sections: [
                    {
                        title: '基本信息',
                        include: ['name', 'type', 'rarity', 'origin']
                    },
                    {
                        title: '详细描述',
                        include: ['function', 'description']
                    }
                ]
            },
            null,
            2
        )
    },
    {
        name: '剧情卡 (Plot)',
        description: '记录剧情大纲、事件冲突和关键节点。',
        json_schema: JSON.stringify(
            {
                type: 'object',
                properties: {
                    title: { type: 'string', title: '剧情标题' },
                    type: { type: 'string', title: '类型', enum: ['主线', '支线', '日常', '回忆'] },
                    summary: { type: 'string', title: '梗概', format: 'textarea' },
                    conflict: { type: 'string', title: '主要冲突', format: 'textarea' },
                    characters: { type: 'array', title: '登场人物', items: { type: 'string' } },
                    outcome: { type: 'string', title: '结局/影响', format: 'textarea' }
                },
                required: ['title']
            },
            null,
            2
        ),
        ui_layout: JSON.stringify(
            {
                sections: [
                    {
                        title: '基本信息',
                        include: ['title', 'type', 'characters']
                    },
                    {
                        title: '剧情内容',
                        include: ['summary', 'conflict', 'outcome']
                    }
                ]
            },
            null,
            2
        )
    }
]
