import request from '../utils/request'

export function login(username: string, password: string) {
  return request.post('/auth/login', { username, password })
}

export function register(data: {
  username: string
  password: string
  real_name: string
  user_type: string
  contact_info?: string
  // v6.10.0：对齐 v6.9.13 注册契约——PROSPECT 选填画像字段
  phone?: string
  wechat?: string
  age?: number
  education?: string
}) {
  return request.post('/auth/register', data)
}

export function getMe() {
  return request.get('/users/me')
}

export function updateMe(data: Record<string, any>) {
  return request.put('/users/me', data)
}

