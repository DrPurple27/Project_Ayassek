import { useEffect } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNRSStore } from '@/store/nrs'

export function useNRSRealtime() {
  const addEntityOptimistic = useNRSStore((s) => s.addEntityOptimistic)
  const addFactOptimistic = useNRSStore((s) => s.addFactOptimistic)
  const addNeuronOptimistic = useNRSStore((s) => s.addNeuronOptimistic)
  const updateEntityOptimistic = useNRSStore((s) => s.updateEntityOptimistic)
  const removeEntityOptimistic = useNRSStore((s) => s.removeEntityOptimistic)

  useWebSocket({
    sessionId: 'default',
    onMessage: (msg) => {
      switch (msg.type) {
        case 'nrs.remembered': {
          const { entity_name, category, x, y, summary } = msg.data
          if (entity_name && category) {
            addEntityOptimistic({
              id: `entity:${category}:${entity_name}`,
              type: 'entity',
              title: entity_name,
              category,
              summary: summary || '',
              facts_count: 0,
              x: x ?? null,
              y: y ?? null,
            })
          }
          break
        }
        case 'entity.created': {
          const { name, category, summary, x, y } = msg.data
          if (name && category) {
            addEntityOptimistic({
              id: `entity:${category}:${name}`,
              type: 'entity',
              title: name,
              category,
              summary: summary || '',
              facts_count: 0,
              x: x ?? null,
              y: y ?? null,
            })
          }
          break
        }
        case 'entity.updated': {
          const { name, category, summary, x, y } = msg.data
          if (name && category) {
            const id = `entity:${category}:${name}`
            updateEntityOptimistic(id, {
              summary: summary ?? undefined,
              x: x ?? undefined,
              y: y ?? undefined,
            })
          }
          break
        }
        case 'entity.deleted': {
          const { name, category } = msg.data
          if (name && category) {
            removeEntityOptimistic(`entity:${category}:${name}`)
          }
          break
        }
        case 'fact.added': {
          const { entity_name, category, text, status } = msg.data
          if (entity_name && category) {
            const entityId = `entity:${category}:${entity_name}`
            const factId = `fact:${entityId}:${Date.now()}`
            addFactOptimistic(entityId, {
              id: factId,
              title: text?.slice(0, 80) || 'New fact',
              category,
              status: status || 'active',
            })
          }
          break
        }
        case 'neuron.created': {
          const { title, content, x, y } = msg.data
          if (title) {
            const id = `neuron:${title.replace(/[^a-zA-Z0-9]/g, '_')}`
            addNeuronOptimistic({
              id,
              type: 'neuron',
              title,
              summary: content || '',
              category: 'neuron',
              status: 'active',
              x: x ?? null,
              y: y ?? null,
            })
          }
          break
        }
      }
    },
  })
}