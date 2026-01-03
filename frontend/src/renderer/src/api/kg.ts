import request from './request'

export interface GraphData {
  nodes: any[]
  edges: any[]
}

export const getProjectGraph = (projectId: number, pov_character?: string) => {
  return request.get<GraphData>(`/kg/project/${projectId}/graph`, {
    params: { pov_character }
  })
}
