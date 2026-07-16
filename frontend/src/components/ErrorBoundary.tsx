import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex items-center justify-center h-full bg-cb-bg">
          <div className="text-center p-8 max-w-md">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-cb-red/10 flex items-center justify-center">
              <span className="text-cb-red text-lg font-bold">!</span>
            </div>
            <p className="text-cb-text-bright text-sm font-medium mb-1">Panel failed to load</p>
            <p className="text-cb-muted text-xs mb-4 font-mono">{this.state.error?.message}</p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="cb-btn-neon text-sm px-4 py-2 rounded-lg"
            >
              Retry
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}