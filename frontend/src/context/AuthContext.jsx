import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { clearStoredSession, getStoredSession, saveStoredSession } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(getStoredSession)

  useEffect(() => {
    const onUnauthorized = () => setSession(null)
    window.addEventListener('citycare:unauthorized', onUnauthorized)
    return () => window.removeEventListener('citycare:unauthorized', onUnauthorized)
  }, [])

  const value = useMemo(() => ({
    session,
    user: session?.user ?? null,
    signIn(nextSession) {
      saveStoredSession(nextSession)
      setSession(nextSession)
    },
    signOut() {
      clearStoredSession()
      setSession(null)
    },
  }), [session])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

