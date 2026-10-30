import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { Atmosphere } from '@/components/Atmosphere'
import { Layout } from '@/components/Layout'
import { Toaster } from '@/components/ui/sonner'
import { api, type Me } from '@/lib/api'
import { Dashboard } from '@/pages/Dashboard'
import { Hauntings } from '@/pages/Hauntings'
import { Landing } from '@/pages/Landing'
import { Seance } from '@/pages/Seance'

export default function App() {
  // undefined = still checking the session cookie, null = logged out.
  const [me, setMe] = useState<Me | null | undefined>(undefined)

  useEffect(() => {
    api<Me>('/api/me')
      .then(setMe)
      .catch(() => setMe(null))
  }, [])

  if (me === undefined) return <Atmosphere />

  return (
    <BrowserRouter>
      <Atmosphere />
      {/* Content sits above the fixed atmosphere layer. */}
      <div className="relative z-10">
        {me === null ? (
          <Landing />
        ) : (
          <Routes>
            <Route element={<Layout me={me} onMeChange={setMe} onLogout={() => setMe(null)} />}>
              <Route index element={<Dashboard me={me} />} />
              <Route path="repos/:id" element={<Seance me={me} />} />
              <Route path="hauntings" element={<Hauntings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        )}
      </div>
      <Toaster position="bottom-right" />
    </BrowserRouter>
  )
}
