import request from './request'

export interface CardPackageImportRequest {
    target_parent_id?: number | null
    package_data: any
}

export function exportCardPackage(cardId: number) {
    return request.post(`/cards/${cardId}/export`)
}

export function importCardPackage(projectId: number, data: CardPackageImportRequest) {
    return request.post(`/projects/${projectId}/import-package`, data)
}
