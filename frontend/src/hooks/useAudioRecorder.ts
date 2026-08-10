import { useRef, useCallback } from 'react'

interface UseAudioRecorderReturn {
  start: () => Promise<void>
  stop: () => Promise<Blob>
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    mediaRecorderRef.current = recorder
    chunksRef.current = []

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data)
      }
    }

    recorder.start()
  }, [])

  const stop = useCallback((): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current
      if (!recorder) {
        reject(new Error('No recorder active'))
        return
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        // Stop all tracks to release mic
        recorder.stream.getTracks().forEach(t => t.stop())
        resolve(blob)
      }

      recorder.stop()
    })
  }, [])

  return { start, stop }
}
