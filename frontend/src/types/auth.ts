export type UserVisibility = 'full' | 'technician' | 'commercial'

export type AuthUser = {
  id: number
  user_id?: string
  username: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  is_staff: boolean
  date_joined: string
  last_login: string | null
  company_id?: string | null
  job_title?: string
  visibility?: UserVisibility
}
