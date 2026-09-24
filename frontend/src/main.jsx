import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.scss';
import App from './App';

// ── Error boundary — catches render errors and shows them instead of blank page
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(err) {
    return { error: err };
  }
  componentDidCatch(err, info) {
    console.error('[ErrorBoundary]', err, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: '2rem',
          fontFamily: 'IBM Plex Mono, monospace',
          fontSize: '0.875rem',
          background: '#161616',
          color: '#ff8389',
          minHeight: '100vh',
          whiteSpace: 'pre-wrap',
        }}>
          <strong style={{ fontSize: '1rem' }}>⚠ Render error — check this then reload</strong>
          {'\n\n'}
          {this.state.error?.toString()}
          {'\n\n'}
          {this.state.error?.stack}
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
