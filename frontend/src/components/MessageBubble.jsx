import React, { useRef, useEffect } from 'react';
import gsap from 'gsap';

export default function MessageBubble({ msg, index, isLast }) {
  const wrapperRef = useRef(null);

  useEffect(() => {
    if (isLast) {
      // Animate entry for new messages
      gsap.fromTo(wrapperRef.current,
        { opacity: 0, y: 30, scale: 0.95 },
        { opacity: 1, y: 0, scale: 1, duration: 0.6, ease: "back.out(1.5)" }
      );
    } else {
      // Ensure previous messages are visible immediately
      gsap.set(wrapperRef.current, { opacity: 1, y: 0, scale: 1 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLast]);

  // Optionally animate sources metadata when it arrives
  const sourcesRef = useRef(null);
  useEffect(() => {
    if (msg.metadata && msg.metadata.sources && sourcesRef.current) {
      gsap.fromTo(sourcesRef.current, 
        { opacity: 0, height: 0 }, 
        { opacity: 1, height: "auto", duration: 0.5, ease: "power2.out" }
      );
    }
  }, [msg.metadata]);

  const hasMetadata = msg.role === 'assistant' && msg.metadata;
  const sources = hasMetadata && msg.metadata.sources;
  const confidenceLevel = hasMetadata && msg.metadata.confidence_level;
  const confidenceEmoji = hasMetadata && msg.metadata.confidence_emoji;

  return (
    <div ref={wrapperRef} className={`message-wrapper ${msg.role}`}>
      <div className="message-bubble">
        {confidenceLevel && (
          <div className="message-confidence-badge" style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            textTransform: 'uppercase',
            letterSpacing: '1.2px',
            fontWeight: '600',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            padding: '4px 10px',
            borderRadius: '20px',
            marginBottom: '12px'
          }}>
            <span>{confidenceEmoji}</span>
            <span style={{ color: 'var(--text-secondary)' }}>Confidence:</span>
            <span style={{
              color: confidenceLevel === 'HIGH' ? '#10b981' : confidenceLevel === 'MEDIUM' ? '#f59e0b' : '#ef4444'
            }}>{confidenceLevel}</span>
          </div>
        )}

        <div className="message-content whitespace-pre-wrap">{msg.content}</div>

        {sources && sources.length > 0 && (
          <div 
            ref={sourcesRef} 
            className="message-sources" 
            style={{
              marginTop: '16px',
              paddingTop: '12px',
              borderTop: '1px solid var(--border-color)',
              fontSize: '12px'
            }}
          >
            <div style={{ color: 'var(--text-secondary)', fontWeight: '500', marginBottom: '6px', letterSpacing: '0.5px' }}>Sources:</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {sources.map((src, i) => (
                <div key={i} className="source-item" style={{ color: 'rgba(255, 255, 255, 0.65)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>{src}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

