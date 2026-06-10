import { Component } from "react";

// Converts a render crash into a visible message instead of a blank page, and
// logs the error/stack so the real cause is recoverable. Give it a `key` tied
// to the active tab so switching tabs remounts it and clears the error.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Surfaced in the console with the component stack for diagnosis.
    console.error("Render error:", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      const err = this.state.error;
      return (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 space-y-3">
          <div className="text-[15px] font-semibold text-red-700">
            Something went wrong rendering this view
          </div>
          <pre className="text-[12px] text-red-600 whitespace-pre-wrap overflow-auto max-h-60">
            {String(err?.stack || err?.message || err)}
          </pre>
          <button
            onClick={() => window.location.reload()}
            className="rounded-xl bg-action-dark px-4 py-2 text-[13px] font-semibold text-text-invert"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
