import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import gsap from 'gsap';

// Components
import Sidebar from './components/Sidebar';
import MessageBubble from './components/MessageBubble';
import InputArea from './components/InputArea';
import AuthModal from './components/AuthModal';
import UserProfileDropdown from './components/UserProfileDropdown';
import './App.css';

export const API_BASE = import.meta.env.VITE_API_BASE || (
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api'
    : '/api'
);


// --- User Session Identity ---
let savedEmail = localStorage.getItem('researchmind_user_email');
export let userId = localStorage.getItem('researchmind_user_id') || sessionStorage.getItem('researchmind_user_id');
let initialIsLoggedIn = !!savedEmail;

if (!userId) {
  userId = 'usr_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  sessionStorage.setItem('researchmind_user_id', userId);
}

// Move legacy localStorage users to sessionStorage if they aren't logged in
if (!initialIsLoggedIn && localStorage.getItem('researchmind_user_id')) {
  sessionStorage.setItem('researchmind_user_id', userId);
  localStorage.removeItem('researchmind_user_id');
}

axios.interceptors.request.use((config) => {
  config.headers['X-User-ID'] = userId;
  return config;
});
// -----------------------------

function App() {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [sessions, setSessions] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [sysStatus, setSysStatus] = useState({ documents_loaded: 0 });
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(initialIsLoggedIn);
  const [userEmail, setUserEmail] = useState(savedEmail || '');
  const messagesEndRef = useRef(null);
  const emptyStateRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    // Session ID setup
    let sid = localStorage.getItem('researchmind_session_id');
    if (!sid) {
      sid = "sess_" + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('researchmind_session_id', sid);
    }
    setSessionId(sid);

    axios.get(`${API_BASE}/status`).then(res => setSysStatus(res.data)).catch(console.error);
    
    // Load history from backend
    axios.get(`${API_BASE}/chat/history/${sid}`).then(res => {
      if (res.data.history && res.data.history.length > 0) {
        setMessages(res.data.history);
      }
    }).catch(console.error);

    // Fetch all sessions
    fetchSessions();
    
    // Background glow animation
    gsap.to('.bg-glow', {
      rotation: 360,
      duration: 120,
      repeat: -1,
      ease: "linear"
    });
  }, []);

  useEffect(() => {
    if (messages.length === 0 && emptyStateRef.current) {
      gsap.fromTo(emptyStateRef.current, 
        { opacity: 0, scale: 0.9 },
        { opacity: 1, scale: 1, duration: 1, ease: "power3.out", delay: 0.2 }
      );
    }
  }, [messages.length]);

  const fetchSessions = () => {
    axios.get(`${API_BASE}/chat/sessions`).then(res => {
      setSessions(res.data.sessions);
    }).catch(console.error);
  };

  const handleLoginSuccess = (newUserId, email) => {
    userId = newUserId;
    localStorage.setItem('researchmind_user_id', userId);
    localStorage.setItem('researchmind_user_email', email);
    sessionStorage.removeItem('researchmind_user_id');
    setIsLoggedIn(true);
    setUserEmail(email);
    fetchSessions();
  };

  const handleLogout = () => {
    localStorage.removeItem('researchmind_user_id');
    localStorage.removeItem('researchmind_user_email');
    setIsLoggedIn(false);
    setUserEmail('');
    // Generate new guest ID
    userId = 'usr_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    sessionStorage.setItem('researchmind_user_id', userId);
    setSessions([]);
    setMessages([]);
    setSessionId("sess_" + Math.random().toString(36).substring(2, 15));
  };

  const handlePin = (sid, isPinned) => {
    axios.post(`${API_BASE}/chat/sessions/${sid}/pin?is_pinned=${!isPinned}`).then(() => fetchSessions());
  };

  const handleArchive = (sid, isArchived) => {
    axios.post(`${API_BASE}/chat/sessions/${sid}/archive?is_archived=${!isArchived}`).then(() => fetchSessions());
  };

  const handleDelete = (sid) => {
    axios.delete(`${API_BASE}/chat/sessions/${sid}`).then(() => {
      fetchSessions();
      if (sessionId === sid) handleNewChat();
    });
  };

  const handleNewChat = () => {
    const sid = "sess_" + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('researchmind_session_id', sid);
    setSessionId(sid);
    setMessages([]);
    setSysStatus(prev => ({ ...prev, doc_names: [], doc_heading: null }));
  };

  const handleSelectSession = (sid) => {
    localStorage.setItem('researchmind_session_id', sid);
    setSessionId(sid);
    setMessages([]);
    setSysStatus(prev => ({ ...prev, doc_names: [], doc_heading: null }));
    
    // Optimistically fetch the status of the selected session
    axios.get(`${API_BASE}/status?session_id=${sid}`).then(res => {
        setSysStatus(prev => ({ ...prev, doc_names: res.data.doc_names, doc_heading: res.data.doc_heading }));
    }).catch(console.error);

    axios.get(`${API_BASE}/chat/history/${sid}`).then(res => {
      if (res.data.history) {
        setMessages(res.data.history);
      }
    }).catch(console.error);
  };

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files.length) return;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    formData.append('session_id', sessionId); // Attach session ID so backend can isolate the vector store

    setIsUploading(true);
    try {
      const res = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSysStatus(prev => ({ 
        ...prev, 
        documents_loaded: res.data.total_documents, 
        doc_heading: res.data.doc_heading,
        doc_names: res.data.doc_names
      }));
      setMessages(prev => [...prev, { role: 'assistant', content: "Document analyzed. Ready for your questions.", metadata: null }]);
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error uploading files");
    } finally {
      setIsUploading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || sysStatus.documents_loaded === 0) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    setMessages(prev => [...prev, { role: 'assistant', content: '', metadata: null }]);

    try {
      const payload = { session_id: sessionId, query: userMessage.content, history: messages };
      if (messages.length <= 2 && sysStatus.doc_heading) {
        payload.doc_heading = sysStatus.doc_heading;
      }
      
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-User-ID': userId
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        let errorMessage = "Error generating response";
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          const errorText = await response.text();
          errorMessage = errorText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      let done = false;
      let textBuffer = "";

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          textBuffer += chunk;
          
          const lines = textBuffer.split('\n\n');
          textBuffer = lines.pop();

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.substring(6);
              if (dataStr === '[DONE]') break;
              
              const data = JSON.parse(dataStr);
              if (data.type === 'metadata') {
                setMessages(prev => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  newMsgs[newMsgs.length - 1] = { ...lastMsg, metadata: data };
                  return newMsgs;
                });
              } else if (data.type === 'chunk') {
                setMessages(prev => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  newMsgs[newMsgs.length - 1] = { ...lastMsg, content: lastMsg.content + data.content };
                  return newMsgs;
                });
              } else if (data.type === 'error') {
                 setMessages(prev => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  newMsgs[newMsgs.length - 1] = { ...lastMsg, content: lastMsg.content + `\n\n[Error: ${data.content}]` };
                  return newMsgs;
                });
              }
            }
          }
        }
      }
    } catch (err) {
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1].content = `❌ ${err.message}`;
        return newMsgs;
      });
    } finally {
      setIsLoading(false);
      fetchSessions(); // Update sidebar with new session if it was the first message
    }
  };

  return (
    <>
      <div className="bg-glow"></div>
      <div className="app-container">
        <Sidebar 
          sysStatus={sysStatus} 
          isUploading={isUploading} 
          onFileUpload={handleFileUpload}
          sessions={sessions}
          activeSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onPin={handlePin}
          onArchive={handleArchive}
          onDelete={handleDelete}
          isLoggedIn={isLoggedIn}
          userEmail={userEmail}
          onOpenAuth={() => setIsAuthModalOpen(true)}
          onLogout={handleLogout}
        />
        <div className="main-content">
          {isLoggedIn && (
            <UserProfileDropdown userEmail={userEmail} onLogout={handleLogout} />
          )}

          {isUploading && (
            <div className="upload-overlay">
              <div className="upload-spinner"></div>
              <h2 style={{ fontSize: '18px', fontWeight: '400', letterSpacing: '1px' }}>Analyzing Document</h2>
            </div>
          )}
          
          {sysStatus.doc_names && sysStatus.doc_names.length > 0 && (
            <div className="active-context-bar" style={{ justifyContent: 'center', background: 'transparent', borderBottom: 'none', padding: '24px 0 0 0' }}>
              <div className="context-files" style={{ 
                background: 'rgba(255,255,255,0.03)', 
                border: '1px solid rgba(255,255,255,0.08)', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '10px',
                padding: '6px 16px',
                borderRadius: '20px'
              }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#8b5cf6', boxShadow: '0 0 10px #8b5cf6', animation: 'pulse 2s infinite' }}></span>
                <span style={{ color: 'var(--text-secondary)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: '500' }}>Synchronized:</span>
                <span style={{ color: '#e5e5e5', fontSize: '13px' }}>{sysStatus.doc_names.join(', ')}</span>
              </div>
            </div>
          )}
          
          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="empty-state" ref={emptyStateRef}>
                <div className="empty-icon-wrapper">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                  </svg>
                </div>
                <h2 className="empty-title">Ready to Assist</h2>
                <p className="empty-desc">Upload some research documents from the sidebar, then ask me anything about them to get AI-powered insights with citations.</p>
              </div>
            ) : (
              <div className="chat-thread">
                {messages.map((msg, idx) => (
                  <MessageBubble 
                    key={idx} 
                    msg={msg} 
                    index={idx}
                    isLast={idx === messages.length - 1} 
                  />
                ))}
                
                {isLoading && messages[messages.length - 1]?.role === 'user' && (
                  <div className="message-wrapper assistant" style={{ opacity: 1 }}>
                    <div className="message-bubble" style={{ display: 'inline-block', padding: '16px 20px' }}>
                      <div className="typing-dots">
                        <span className="typing-dot"></span>
                        <span className="typing-dot"></span>
                        <span className="typing-dot"></span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} style={{ height: '1px' }} />
              </div>
            )}
          </div>

          <InputArea 
            input={input}
            setInput={setInput}
            handleSend={handleSend}
            disabled={sysStatus.documents_loaded === 0 || isLoading}
            placeholder={sysStatus.documents_loaded === 0 ? "Upload a document first..." : "Ask a question about the research..."}
          />
        </div>
      </div>
      
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={() => setIsAuthModalOpen(false)} 
        onLoginSuccess={handleLoginSuccess}
        apiBase={API_BASE}
      />
    </>
  );
}

export default App;
