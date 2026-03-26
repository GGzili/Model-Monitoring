import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export const getModels    = ()           => http.get('/models')
export const createModel  = (data)       => http.post('/models', data)
export const updateModel  = (id, data)   => http.put(`/models/${id}`, data)
export const deleteModel  = (id)         => http.delete(`/models/${id}`)
export const checkNow     = (id)         => http.post(`/models/${id}/check`)
export const restartModel = (id)         => http.post(`/models/${id}/restart`)
export const getHistory   = (id, limit=100) => http.get(`/models/${id}/history`, { params: { limit } })
export const getDashboard = ()           => http.get('/dashboard')
