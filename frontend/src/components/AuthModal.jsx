import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Mail, Lock, ArrowLeft, KeyRound, CheckCircle2 } from 'lucide-react';

export default function AuthModal({ isOpen, onClose, onLoginSuccess, apiBase }) {
  const [view, setView] = useState('login'); // 'login' | 'register' | 'forgot' | 'reset-success'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setEmail('');
      setPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setError('');
      setView('login');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const endpoint = view === 'login' ? '/auth/login' : '/auth/register';
      const res = await axios.post(`${apiBase}${endpoint}`, { email, password });
      onLoginSuccess(res.data.user_id, res.data.email);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await axios.post(`${apiBase}/auth/reset-password`, { 
        email, 
        new_password: newPassword 
      });
      setView('reset-success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Password reset failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const isLogin = view === 'login';

  // --- Reset Success View ---
  if (view === 'reset-success') {
    return (
      <div className="auth-modal-overlay" onClick={onClose}>
        <div className="auth-modal-content" onClick={e => e.stopPropagation()}>
          <button className="auth-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <CheckCircle2 size={48} style={{ color: '#10b981', marginBottom: '16px' }} />
            <h2>Password Reset!</h2>
            <p className="auth-subtitle">
              Your password has been updated successfully. You can now sign in with your new password.
            </p>
            <button 
              className="auth-submit-btn" 
              style={{ marginTop: '20px' }}
              onClick={() => {
                setPassword('');
                setNewPassword('');
                setConfirmPassword('');
                setError('');
                setView('login');
              }}
            >
              Back to Sign In
            </button>
          </div>
        </div>
      </div>
    );
  }

  // --- Forgot Password View ---
  if (view === 'forgot') {
    return (
      <div className="auth-modal-overlay" onClick={onClose}>
        <div className="auth-modal-content" onClick={e => e.stopPropagation()}>
          <button className="auth-close-btn" onClick={onClose}>
            <X size={20} />
          </button>

          <button 
            className="auth-switch-btn" 
            onClick={() => { setError(''); setView('login'); }}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '8px', fontSize: '13px' }}
          >
            <ArrowLeft size={14} /> Back to Sign In
          </button>

          <h2>Reset Password</h2>
          <p className="auth-subtitle">
            Enter your email and choose a new password.
          </p>

          <form onSubmit={handleResetPassword} className="auth-form">
            {error && <div className="auth-error">{error}</div>}
            
            <div className="input-group">
              <Mail size={18} className="input-icon" />
              <input 
                type="email" 
                placeholder="Email Address" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required 
              />
            </div>

            <div className="input-group">
              <KeyRound size={18} className="input-icon" />
              <input 
                type="password" 
                placeholder="New Password" 
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required 
                minLength={6}
              />
            </div>

            <div className="input-group">
              <Lock size={18} className="input-icon" />
              <input 
                type="password" 
                placeholder="Confirm New Password" 
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required 
                minLength={6}
              />
            </div>

            <button type="submit" className="auth-submit-btn" disabled={isLoading}>
              {isLoading ? 'Resetting...' : 'Reset Password'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- Login / Register View ---
  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal-content" onClick={e => e.stopPropagation()}>
        <button className="auth-close-btn" onClick={onClose}>
          <X size={20} />
        </button>
        
        <h2>{isLogin ? 'Welcome Back' : 'Create Account'}</h2>
        <p className="auth-subtitle">
          {isLogin 
            ? 'Sign in to access your saved documents and chat history.' 
            : 'Sign up to permanently save your chat history and documents.'}
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}
          
          <div className="input-group">
            <Mail size={18} className="input-icon" />
            <input 
              type="email" 
              placeholder="Email Address" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required 
            />
          </div>
          
          <div className="input-group">
            <Lock size={18} className="input-icon" />
            <input 
              type="password" 
              placeholder="Password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required 
            />
          </div>

          {isLogin && (
            <div style={{ textAlign: 'right', marginTop: '-4px', marginBottom: '4px' }}>
              <button 
                type="button"
                className="auth-switch-btn" 
                onClick={() => { setError(''); setView('forgot'); }}
                style={{ fontSize: '12px', opacity: 0.7 }}
              >
                Forgot Password?
              </button>
            </div>
          )}

          <button type="submit" className="auth-submit-btn" disabled={isLoading}>
            {isLoading ? 'Please wait...' : (isLogin ? 'Sign In' : 'Create Account')}
          </button>
        </form>

        <div className="auth-switch">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button className="auth-switch-btn" onClick={() => { setError(''); setView(isLogin ? 'register' : 'login'); }}>
            {isLogin ? 'Sign Up' : 'Sign In'}
          </button>
        </div>
      </div>
    </div>
  );
}
