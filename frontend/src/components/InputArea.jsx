import React, { useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import gsap from 'gsap';

export default function InputArea({ input, setInput, handleSend, disabled, placeholder }) {
  const containerRef = useRef(null);

  useEffect(() => {
    // Slide up animation on load
    gsap.fromTo(containerRef.current,
      { y: 100, opacity: 0 },
      { y: 0, opacity: 1, duration: 1, ease: "power3.out", delay: 0.3 }
    );
  }, []);

  return (
    <div className="input-container" ref={containerRef}>
      <form onSubmit={handleSend} className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="chat-input"
        />
        <button 
          type="submit" 
          disabled={disabled || !input.trim()}
          className="send-btn"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
