const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function transcribeAudio(
  blob: Blob,
  token: string,
): Promise<{ transcript: string; duration_seconds: number | null }> {
  const formData = new FormData()
  formData.append('audio', blob, 'recording.webm')

  const res = await fetch(`${API_URL}/api/listen`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })

  if (!res.ok) {
    throw new Error(`Transcription failed: ${res.status} ${res.statusText}`)
  }

  return res.json() as Promise<{ transcript: string; duration_seconds: number | null }>
}

export async function synthesizeSpeech(text: string, token: string): Promise<Blob> {
  const res = await fetch(`${API_URL}/api/speak`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text }),
  })

  if (!res.ok) {
    throw new Error(`Speech synthesis failed: ${res.status} ${res.statusText}`)
  }

  return res.blob()
}
