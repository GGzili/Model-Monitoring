import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

/** 去掉 undefined、把 Vue reactive 转成可 JSON 序列化的纯对象，避免 axios 丢字段（如 ssh_port） */
function jsonPlain(obj) {
  return JSON.parse(JSON.stringify(obj))
}

export const getModels    = ()           => http.get('/models')
export const createModel  = (data)       => http.post('/models', jsonPlain(data))
export const updateModel  = (id, data)   => http.put(`/models/${id}`, data)
export const deleteModel  = (id)         => http.delete(`/models/${id}`)
export const checkNow     = (id)         => http.post(`/models/${id}/check`)
export const restartModel = (id)         => http.post(`/models/${id}/restart`)
export const getHistory   = (id, limit=100) => http.get(`/models/${id}/history`, { params: { limit } })
export const getDashboard = ()           => http.get('/dashboard')
