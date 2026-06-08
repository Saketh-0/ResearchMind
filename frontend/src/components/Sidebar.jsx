import React, { useRef, useEffect, useState } from 'react';
import { UploadCloud, PlusCircle, MessageSquare, MoreVertical, Pin, Archive, Trash2, LogIn } from 'lucide-react';
import gsap from 'gsap';

export default function Sidebar({ 
  sysStatus, 
  isUploading, 
  onFileUpload, 
  sessions, 
  onNewChat, 
  onSelectSession, 
  activeSessionId, 
  onPin, 
  onArchive,
  onDelete,
  isLoggedIn,
  onOpenAuth
}) {
  const sidebarRef = useRef(null);
  const uploadBtnRef = useRef(null);
  const [openDropdown, setOpenDropdown] = useState(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.history-item-wrapper')) {
        setOpenDropdown(null);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  useEffect(() => {
    // Entrance animation
    gsap.fromTo(sidebarRef.current, 
      { x: -350, opacity: 0 }, 
      { x: 0, opacity: 1, duration: 1, ease: "power4.out" }
    );
  }, []);

  const handleUploadHover = (isEnter) => {
    if (isUploading) return;
    gsap.to(uploadBtnRef.current, {
      scale: isEnter ? 1.02 : 1,
      boxShadow: isEnter ? '0 8px 25px rgba(139, 92, 246, 0.4)' : '0 4px 15px rgba(139, 92, 246, 0.3)',
      duration: 0.3,
      ease: "power2.out"
    });
  };

  return (
    <div className="sidebar" ref={sidebarRef}>
      <div className="brand-container">
        <h1 className="brand-title">ResearchMind</h1>
        <p className="brand-subtitle">AI Intelligence</p>
      </div>

      <div className="upload-card">
        <div className="upload-icon-container">
          <UploadCloud size={28} />
        </div>
        <div>
          <h3 className="upload-title">Knowledge Base</h3>
          <p className="upload-desc">Upload PDFs to embed new intelligence</p>
        </div>
        
        <div className="file-input-wrapper">
          <button 
            ref={uploadBtnRef}
            className="btn-primary" 
            disabled={isUploading}
            onMouseEnter={() => handleUploadHover(true)}
            onMouseLeave={() => handleUploadHover(false)}
          >
            {isUploading ? (
              <div className="typing-dots">
                <span className="typing-dot" style={{ backgroundColor: '#fff' }}></span>
                <span className="typing-dot" style={{ backgroundColor: '#fff' }}></span>
                <span className="typing-dot" style={{ backgroundColor: '#fff' }}></span>
              </div>
            ) : 'Select Documents'}
          </button>
          <input 
            type="file" 
            multiple 
            accept=".pdf" 
            onChange={onFileUpload} 
            disabled={isUploading} 
          />
        </div>
      </div>

      <button className="new-chat-premium-btn" onClick={onNewChat}>
        <div className="btn-content">
          <PlusCircle size={18} />
          <span>New Chat</span>
        </div>
        <div className="btn-glow"></div>
      </button>

      <div className="history-section" style={{ marginTop: '24px', flex: 1, overflowY: 'auto' }}>
        <h4 style={{ color: 'var(--text-secondary)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px', paddingLeft: '4px' }}>Recent Chats</h4>
        <div className="history-list" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {sessions && sessions.length > 0 ? (
            sessions.map((sess, idx) => (
              <div 
                key={sess.session_id} 
                className={`history-item-wrapper ${activeSessionId === sess.session_id ? 'active' : ''}`}
                style={{ animationDelay: `${idx * 0.05}s` }}
              >
                <button 
                  className="history-item"
                  onClick={() => onSelectSession(sess.session_id)}
                >
                  <MessageSquare size={16} color={sess.is_pinned ? '#8b5cf6' : 'var(--text-secondary)'} style={{ flexShrink: 0 }} />
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sess.title}</span>
                </button>
                <button 
                  className="history-actions-btn"
                  onClick={(e) => { 
                    e.stopPropagation(); 
                    setOpenDropdown(openDropdown === sess.session_id ? null : sess.session_id); 
                  }}
                >
                  <MoreVertical size={16} />
                </button>

                {openDropdown === sess.session_id && (
                  <div className="history-dropdown">
                    <button className="history-dropdown-item" onClick={(e) => { e.stopPropagation(); onPin(sess.session_id, sess.is_pinned); setOpenDropdown(null); }}>
                      <Pin size={14} /> {sess.is_pinned ? 'Unpin' : 'Pin'}
                    </button>
                    <button className="history-dropdown-item" onClick={(e) => { e.stopPropagation(); onArchive(sess.session_id, sess.is_archived); setOpenDropdown(null); }}>
                      <Archive size={14} /> Archive
                    </button>
                    <button className="history-dropdown-item delete" onClick={(e) => { e.stopPropagation(); onDelete(sess.session_id); setOpenDropdown(null); }}>
                      <Trash2 size={14} /> Delete
                    </button>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div style={{ padding: '0 4px', color: 'var(--text-secondary)', fontSize: '13px', fontStyle: 'italic', marginTop: '8px' }}>
              No recent chats
            </div>
          )}
        </div>
      </div>

      {!isLoggedIn && (
        <button className="login-to-save-btn" onClick={onOpenAuth}>
          <LogIn size={18} />
          Sign in to Save
        </button>
      )}

    </div>
  );
}
