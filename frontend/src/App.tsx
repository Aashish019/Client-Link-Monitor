import { useEffect, useState, useRef } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Server,
  Search,
  AlertCircle,
  CheckCircle2,
  RefreshCw
} from 'lucide-react';
import { cn } from './lib/utils';
import { UrlStatus, WebSocketPayload } from './types';

// Components
const StatCard = ({ title, value, subtext, icon: Icon, color, trend }: any) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className="glass-panel p-6 flex flex-col justify-between h-full relative overflow-hidden group"
  >
    <div className={`absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
      <Icon size={64} />
    </div>
    <div className="flex items-center space-x-3 mb-2">
      <div className={`p-2 rounded-lg bg-surfaceHighlight ${color.replace('text-', 'bg-').replace('500', '500/20')}`}>
        <Icon size={20} className={color} />
      </div>
      <h3 className="text-textMuted font-medium text-sm uppercase tracking-wider">{title}</h3>
    </div>
    <div className="z-10">
      <div className="text-3xl font-bold text-text mb-1">{value}</div>
      <div className="text-sm text-textMuted">{subtext}</div>
    </div>
    {trend !== undefined && (
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-surfaceHighlight">
        <motion.div
          className={`h-full ${color.replace('text-', 'bg-')}`}
          initial={{ width: 0 }}
          animate={{ width: `${trend}%` }}
          transition={{ type: "spring", stiffness: 100 }}
        />
      </div>
    )}
  </motion.div>
);

const UrlCard = ({ item }: { item: UrlStatus }) => {
  const isUp = item.status === 'up';
  const [isRestarting, setIsRestarting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleRestart = async () => {
    setIsRestarting(true);
    try {
      await fetch(`http://localhost:8000/api/restart/${item.name}`, { method: 'POST' });
    } catch (e) {
      console.error("Restart failed", e);
    }
    setTimeout(() => setIsRestarting(false), 2000);
  };

  const handleDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete ${item.name}?`)) return;

    setIsDeleting(true);
    try {
      await fetch(`http://localhost:8000/api/clients/${item.name}`, { method: 'DELETE' });
    } catch (e) {
      console.error("Delete failed", e);
      setIsDeleting(false);
    }
  };

  if (isDeleting) return null;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className={cn(
        "glass-panel p-4 flex items-center justify-between border-l-4 group relative",
        isUp ? "border-l-success" : "border-l-warning"
      )}
    >
      <button
        onClick={handleDelete}
        className="absolute top-2 right-2 p-1.5 rounded-full bg-bg/50 text-textMuted hover:bg-red-500/20 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all z-20"
        title="Delete Service"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /></svg>
      </button>

      <div className="flex items-center space-x-4 overflow-hidden">
        <div className={cn(
          "p-3 rounded-full shrink-0",
          isUp ? "bg-success/10 text-success" : "bg-warning/10 text-warning animate-pulse"
        )}>
          {isUp ? <CheckCircle2 size={24} /> : <AlertCircle size={24} />}
        </div>
        <div className="min-w-0">
          <h4 className="font-semibold text-text truncate pr-6">{item.name}</h4>
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-sm text-textMuted hover:text-primary truncate block">
            {item.url}
          </a>
        </div>
      </div>
      <div className="text-right shrink-0 ml-4 flex flex-col items-end">
        {!isUp && (
          <button
            onClick={handleRestart}
            disabled={isRestarting}
            className="mb-2 px-3 py-1 bg-warning/20 hover:bg-warning/30 text-warning text-xs font-bold uppercase tracking-wider rounded border border-warning/50 transition-colors flex items-center space-x-1"
          >
            {isRestarting ? <span>Triggered</span> : <span>Restart</span>}
          </button>
        )}
        <div className={cn(
          "font-bold text-lg",
          isUp ? "text-success" : "text-warning"
        )}>
          {item.status_code || 'ERR'}
        </div>
        <div className="text-xs text-textMuted">
          {isUp ? 'ONLINE' : 'OFFLINE'}
        </div>
      </div>
    </motion.div>
  );
};

// Add Client Modal Component
const AddClientModal = ({ isOpen, onClose, onAdd }: any) => {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAdd(name, url);
    setName('');
    setUrl('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-panel p-6 w-full max-w-md rounded-xl border border-white/10"
      >
        <h2 className="text-xl font-bold mb-4">Add New Service</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-textMuted mb-1">Service Name</label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 bg-surfaceHighlight border border-border rounded-lg focus:ring-2 focus:ring-primary outline-none"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-textMuted mb-1">URL</label>
            <input
              type="url"
              required
              className="w-full px-3 py-2 bg-surfaceHighlight border border-border rounded-lg focus:ring-2 focus:ring-primary outline-none"
              value={url}
              onChange={e => setUrl(e.target.value)}
            />
          </div>
          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 hover:bg-white/5 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary hover:bg-blue-600 rounded-lg font-medium"
            >
              Add Service
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
};

export default function App() {
  const [socketUrl] = useState('ws://localhost:8000/ws');
  const { lastMessage, readyState } = useWebSocket(socketUrl, {
    shouldReconnect: () => true,
    reconnectInterval: 3000,
  });

  const [urls, setUrls] = useState<UrlStatus[]>([]);
  const [filter, setFilter] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (lastMessage !== null) {
      const data: WebSocketPayload = JSON.parse(lastMessage.data);
      if (data.urls) {
        setUrls(data.urls);
        setIsRefreshing(false);
      }
    }
  }, [lastMessage]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetch('http://localhost:8000/api/refresh', { method: 'POST' });
    } catch (e) {
      console.error("Refresh failed", e);
      setIsRefreshing(false);
    }
  };

  const handleAddClient = async (name: string, url: string) => {
    try {
      await fetch('http://localhost:8000/api/clients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, url })
      });
    } catch (e) {
      console.error("Failed to add client", e);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const json = JSON.parse(e.target?.result as string);
        const res = await fetch('http://localhost:8000/api/clients/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(json)
        });

        if (!res.ok) {
          const errData = await res.json();
          console.error("Import error details:", errData);
          alert(`Import failed: ${errData.detail || 'Check console for details'}`);
        } else {
          const data = await res.json();
          alert(`Successfully imported ${data.count} services`);
        }
      } catch (err) {
        console.error("Import failed", err);
        alert("Invalid JSON file or Network Error");
      }
    };
    reader.readAsText(file);
    // Reset input
    event.target.value = '';
  };

  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Live',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Disconnected',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState];

  const filteredUrls = urls.filter(u =>
    u.name.toLowerCase().includes(filter.toLowerCase()) ||
    u.url.toLowerCase().includes(filter.toLowerCase())
  );

  // Stats
  const upCount = urls.filter(u => u.status === 'up').length;
  const downCount = urls.filter(u => u.status === 'down').length;
  const totalCount = urls.length;
  const healthPercent = totalCount > 0 ? (upCount / totalCount) * 100 : 100;

  return (
    <div className="min-h-screen bg-bg text-text p-6 lg:p-10">
      <AddClientModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAdd={handleAddClient}
      />
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        accept=".json"
      />

      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-center mb-10 gap-4">
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
            Client Link Monitor
          </h1>
          <p className="text-textMuted mt-2">Real-time infrastructure dashboard</p>
        </div>
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 bg-surfaceHighlight hover:bg-white/10 rounded-lg text-sm font-medium transition-colors"
          >
            + Add Service
          </button>
          <button
            onClick={handleImportClick}
            className="px-4 py-2 bg-surfaceHighlight hover:bg-white/10 rounded-lg text-sm font-medium transition-colors"
          >
            Import JSON
          </button>
          <div className="h-8 w-px bg-border mx-2"></div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-all flex items-center space-x-2",
              isRefreshing
                ? "bg-surfaceHighlight text-textMuted cursor-wait"
                : "bg-primary text-white hover:bg-blue-600 shadow-lg shadow-blue-900/20"
            )}
          >
            <RefreshCw size={18} className={isRefreshing ? "animate-spin" : ""} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh Now'}</span>
          </button>
          <div className={`px-4 py-2 rounded-full border border-border flex items-center space-x-2 ${readyState === ReadyState.OPEN ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
            <div className={`w-2 h-2 rounded-full ${readyState === ReadyState.OPEN ? 'bg-success animate-pulse' : 'bg-warning'}`} />
            <span className="font-semibold text-sm">{connectionStatus}</span>
          </div>
        </div>
      </header>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <StatCard
          title="Services Up"
          value={`${upCount}/${totalCount}`}
          subtext="Response check every 3m"
          icon={Server}
          color="text-success"
          trend={healthPercent}
        />
        <StatCard
          title="Issues"
          value={downCount}
          subtext={downCount > 0 ? "Action required" : "All systems normal"}
          icon={AlertCircle}
          color={downCount > 0 ? "text-warning" : "text-textMuted"}
          trend={downCount > 0 ? 100 : 0}
        />
      </div>

      {/* Services List */}
      <div className="mb-6 flex flex-col md:flex-row justify-between items-center gap-4">
        <h2 className="text-2xl font-bold">Service Health</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-textMuted" size={18} />
          <input
            type="text"
            placeholder="Search services..."
            className="pl-10 pr-4 py-2 bg-surfaceHighlight border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-text placeholder-textMuted w-full md:w-64 transition-all"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      </div>

      <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <AnimatePresence>
          {filteredUrls.map((item) => (
            <UrlCard key={item.name} item={item} />
          ))}
        </AnimatePresence>
      </motion.div>

      {/* Footer */}
      <footer className="mt-12 text-center text-textMuted text-sm">
        <p>Created by Aashish</p>
      </footer>
    </div>
  );
}
