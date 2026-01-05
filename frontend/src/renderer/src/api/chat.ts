import request from '@renderer/api/request'

export interface ChatSession {
    id: number
    project_id: number
    character_card_id: number
    title: string
    created_at: string
    updated_at: string
}

export interface ChatMessage {
    id: number
    session_id: number
    role: 'user' | 'assistant' | 'system'
    content: string
    created_at: string
}

export interface CreateSessionParams {
    project_id: number
    character_card_id: number
    title?: string
}

export interface SendMessageParams {
    content: string
    llm_config_id?: number
}

export function createSession(data: CreateSessionParams): Promise<ChatSession> {
    return request.post('/chat/sessions', data)
}

export function listSessions(projectId: number): Promise<ChatSession[]> {
    return request.get('/chat/sessions', { project_id: projectId })
}

export function getSession(sessionId: number): Promise<ChatSession> {
    return request.get(`/chat/sessions/${sessionId}`)
}

export function getSessionMessages(sessionId: number): Promise<ChatMessage[]> {
    return request.get(`/chat/sessions/${sessionId}/messages`)
}

export function sendMessage(sessionId: number, data: SendMessageParams): Promise<ChatMessage> {
    return request.post(`/chat/sessions/${sessionId}/messages`, data)
}
