import request from './request'

export function getProjectGraph(projectId: number): Promise<any> {
    return request.get(`/kg/${projectId}`)
}
