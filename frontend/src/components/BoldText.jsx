import React from 'react';

/**
 * Renders a string that uses **text** markdown-style bold markers.
 * Preserves newlines. Each **…** pair becomes a <strong>.
 */
export default function BoldText({ text }) {
  if (!text) return null;
  return (
    <>
      {text.split('\n').map((line, li) => {
        const parts = line.split('**');
        return (
          <React.Fragment key={li}>
            {parts.map((part, pi) =>
              pi % 2 === 1
                ? <strong key={pi} className="dispatch-bold">{part}</strong>
                : <React.Fragment key={pi}>{part}</React.Fragment>
            )}
            {'\n'}
          </React.Fragment>
        );
      })}
    </>
  );
}
