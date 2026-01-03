import request from '@/utils/request'

export interface CardPackageImportRequest {
    target_parent_id?: number | null
    package_data: any
}

export function exportCardPackage(cardId: number) {
    return request({
        url: `/cards/${cardId}/export`,
        method: 'post'
    })
}

export function importCardPackage(projectId: number, data: CardPackageImportRequest) {
    return request({
        url: `/projects/${projectId}/import-package`,
        method: 'post',
        data
    })
}
