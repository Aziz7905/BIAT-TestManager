import React, { useState } from 'react';
import { authService } from '../../core/services/api.service';
import './login.css';


const Login: React.FC = () => {
  const [matricule, setMatricule] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authService.login(matricule, password);
      // Redirect to dashboard on success
      window.location.href = '/dashboard';
    } catch (err: any) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

return (
  <div className="login-page">
    <div className="login-card">
      <div className="login-header">
        <img
          src="/biat-logo.png"
          alt="BIAT IT"
          className="login-logo"
        />
        <h2>BIAT Test Manager</h2>
        <p>Bienvenue</p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Matricule</label>
          <input
            type="text"
            value={matricule}
            onChange={(e) => setMatricule(e.target.value)}
            placeholder="0001"
            required
          />
        </div>

        <div className="form-group">
          <label>Mot de passe</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <button type="submit" disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>
    </div>
  </div>
);

};

export default Login;