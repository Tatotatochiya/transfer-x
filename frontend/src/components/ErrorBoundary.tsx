import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Uncaught error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6">
          <div className="max-w-md w-full rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-8 py-10 text-center">
            <p className="text-4xl font-bold text-slate-700">Oops</p>
            <p className="mt-3 text-base font-semibold text-white">Something went wrong</p>
            <p className="mt-2 text-sm text-slate-400 break-words">{this.state.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-6 rounded-lg bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-400 ring-1 ring-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
