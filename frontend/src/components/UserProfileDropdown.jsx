import React, { useState, useRef, useEffect } from 'react';
import { LogOut, User } from 'lucide-react';

export default function UserProfileDropdown({ userEmail, onLogout }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const initial = userEmail ? userEmail.charAt(0).toUpperCase() : 'U';

  return (
    <div className="user-profile-dropdown" ref={dropdownRef}>
      <button 
        className="profile-avatar-btn" 
        onClick={() => setIsOpen(!isOpen)}
        title={userEmail}
      >
        {initial}
      </button>

      {isOpen && (
        <div className="profile-dropdown-menu">
          <div className="dropdown-header">
            <User size={16} />
            <span className="dropdown-email">{userEmail}</span>
          </div>
          <div className="dropdown-divider"></div>
          <button className="dropdown-logout-btn" onClick={() => {
            setIsOpen(false);
            onLogout();
          }}>
            <LogOut size={16} />
            <span>Logout</span>
          </button>
        </div>
      )}
    </div>
  );
}
