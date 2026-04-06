import { redirect } from "next/navigation"
import { createClient } from "@/lib/supabase/server"
import { ChatApp } from "@/components/chat/chat-app"

export default async function HomePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  // Get user profile if authenticated
  let profile = null
  if (user) {
    const { data } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", user.id)
      .single()
    profile = data
  }

  return <ChatApp user={user} profile={profile} />
}
