import { ChatApp } from "@/components/chat/chat-app"

export default async function HomePage() {
  // No authentication required - users are auto-generated with unique IDs
  return <ChatApp user={null} profile={null} />
}
