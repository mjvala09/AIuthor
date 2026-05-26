import { useState, useEffect, useRef } from 'react';
import { 
  BookOpen, Sparkles, Database, FileSpreadsheet, 
  Settings, Play, Download, PlusCircle, AlertCircle, 
  RotateCw, CheckCircle2, DollarSign, Layers
} from 'lucide-react';

// API interfaces
interface BookBrief {
  topic: string;
  reader_profile: string;
  target_words: number;
  tonality: string;
  genre: string;
  additional_guidelines: string;
  api_key?: string;
}

interface ChapterOutline {
  chapter_number: number;
  title: string;
  description: string;
  target_words: number;
  key_concepts: string[];
}

interface BookOutline {
  title: string;
  subtitle: string;
  author: string;
  brief: BookBrief;
  chapters: ChapterOutline[];
  overall_guidelines: string[];
  style_rules: string[];
}

interface MemoryFact {
  claim: string;
  source_chapter: number;
  verified: boolean;
  citation: string;
}

interface MemoryConcept {
  name: string;
  type: string;
  description: string;
  first_introduced_chapter: number;
  details: Record<string, any>;
}

interface MemoryCallback {
  content: string;
  source_chapter: number;
  target_chapter: number;
  callback_trigger: string;
  applied: boolean;
}

interface MemoryDecision {
  decision: string;
  context: string;
  rationale: string;
  agent: string;
  chapter_number: number;
  timestamp: string;
}

interface BookMemory {
  fact_registry: MemoryFact[];
  concept_bible: MemoryConcept[];
  callback_index: MemoryCallback[];
  tonality_fingerprint: string[];
  decision_log: MemoryDecision[];
}

interface ChapterResult {
  chapter_number: number;
  title: string;
  draft: string;
  humanized: string;
  edited: string;
  final_text: string;
  status: string;
  word_count: number;
  research_report: string;
  fact_check_report: string;
  eval_score: number;
}

interface TokenCostEntry {
  timestamp: string;
  agent_name: string;
  model_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost: number;
}

interface TraceEntry {
  timestamp: string;
  agent_name: string;
  step_name: string;
  input_data: any;
  output_data: any;
  trace_log: string;
}

interface TraceBundle {
  run_id: string;
  traces: TraceEntry[];
  token_cost: TokenCostEntry[];
  total_tokens: number;
  total_cost: number;
}

interface BookResult {
  run_id: string;
  brief: BookBrief;
  outline: BookOutline | null;
  memories: BookMemory;
  chapters: ChapterResult[];
  pdf_path: string;
  docx_path: string;
  status: string;
  created_at: string;
  trace_bundle: TraceBundle | null;
}

interface RubricScore {
  dimension: string;
  score: number;
  feedback: string;
  details: Record<string, any>;
}

interface EvalsReport {
  run_id: string;
  completeness: RubricScore;
  tonality: RubricScore;
  ai_tells: RubricScore;
  fact_coverage: RubricScore;
  callback_recall: RubricScore;
  overall_score: number;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'setup' | 'monitor' | 'memory' | 'evals' | 'reader'>(() => {
    return (localStorage.getItem('aiuthor_active_tab') as any) || 'setup';
  });
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem('openai_api_key') || '');
  
  // Save API key and active tab when they change
  useEffect(() => {
    localStorage.setItem('openai_api_key', apiKey);
  }, [apiKey]);

  useEffect(() => {
    localStorage.setItem('aiuthor_active_tab', activeTab);
  }, [activeTab]);
  
  // Forms
  const [brief, setBrief] = useState<BookBrief>({
    topic: '10-chapter beginner\'s guide to personal finance',
    reader_profile: 'Young adults starting their careers, no prior finance background',
    target_words: 15000,
    tonality: 'Conversational',
    genre: 'Non-Fiction',
    additional_guidelines: 'Focus heavily on compound interest, emergency funds, index funds, and credit score optimization.'
  });
  
  const [insertRequest, setInsertRequest] = useState({
    insert_after_chapter: 4,
    title: 'Chapter 4b: Advanced Investing Strategies',
    description: 'Overview of stock market indexes, ETFs, dollar-cost averaging, and tax-advantaged accounts.',
    target_words: 1500,
    key_concepts: ['ETFs', 'Dollar-Cost Averaging', 'Roth IRA', 'Index Funds']
  });

  // State values
  const [bookList, setBookList] = useState<BookResult[]>(() => {
    const cached = localStorage.getItem('aiuthor_cached_books');
    return cached ? JSON.parse(cached) : [];
  });
  const [currentRunId, setCurrentRunId] = useState<string>(() => {
    return localStorage.getItem('aiuthor_current_run_id') || '';
  });
  const [currentBook, setCurrentBook] = useState<BookResult | null>(() => {
    const cached = localStorage.getItem('aiuthor_current_book');
    return cached ? JSON.parse(cached) : null;
  });
  const [evalReport, setEvalReport] = useState<EvalsReport | null>(() => {
    const cached = localStorage.getItem('aiuthor_eval_report');
    return cached ? JSON.parse(cached) : null;
  });
  const [logs, setLogs] = useState<string[]>(() => {
    const cached = localStorage.getItem('aiuthor_logs');
    return cached ? JSON.parse(cached) : [];
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [activeChapterIndex, setActiveChapterIndex] = useState<number>(0);
  const [memorySubTab, setMemorySubTab] = useState<'facts' | 'concepts' | 'callbacks' | 'decisions'>('facts');
  const [expandedTraceIdx, setExpandedTraceIdx] = useState<number | null>(null);
  
  const pollingRef = useRef<any>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-save persistent values
  useEffect(() => {
    localStorage.setItem('aiuthor_current_run_id', currentRunId);
  }, [currentRunId]);

  useEffect(() => {
    if (currentBook) {
      localStorage.setItem('aiuthor_current_book', JSON.stringify(currentBook));
    } else {
      localStorage.removeItem('aiuthor_current_book');
    }
  }, [currentBook]);

  useEffect(() => {
    if (evalReport) {
      localStorage.setItem('aiuthor_eval_report', JSON.stringify(evalReport));
    } else {
      localStorage.removeItem('aiuthor_eval_report');
    }
  }, [evalReport]);

  useEffect(() => {
    localStorage.setItem('aiuthor_logs', JSON.stringify(logs));
  }, [logs]);

  useEffect(() => {
    localStorage.setItem('aiuthor_cached_books', JSON.stringify(bookList));
  }, [bookList]);

  // Fetch initial books list
  useEffect(() => {
    fetchBooks();
  }, []);

  // Scroll logs to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Poll book status if generation is active
  useEffect(() => {
    if (currentRunId && ['idle', 'outline_planned', 'assembling', 'repairing', 'writing_chapter_1', 'writing_chapter_2', 'writing_chapter_3', 'writing_chapter_4', 'writing_chapter_5', 'writing_chapter_6', 'writing_chapter_7', 'writing_chapter_8', 'writing_chapter_9', 'writing_chapter_10', 'writing_chapter_11'].some(s => currentBook?.status.startsWith(s) || currentBook?.status === 'assembling' || currentBook?.status === 'repairing')) {
      pollingRef.current = setInterval(() => {
        pollStatus(currentRunId);
      }, 3000);
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [currentRunId, currentBook?.status]);

  const fetchBooks = async () => {
    try {
      const res = await fetch('/api/books');
      const data = await res.json();
      setBookList(data);
    } catch (e) {
      console.error("Error fetching books:", e);
    }
  };

  const startGeneration = async () => {
    setLoading(true);
    setLogs(['[System] Initializing Planner Agent...', '[System] Constructing outline schema...']);
    setActiveTab('monitor');
    
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...brief, api_key: apiKey })
      });
      const data: BookResult = await res.json();
      setCurrentRunId(data.run_id);
      setCurrentBook(data);
      setLogs(prev => [...prev, `[System] Book Outline generated: "${data.outline?.title}"`, `[System] Dispatched Researcher and Writer in the background.`]);
    } catch (e) {
      console.error("Error starting book:", e);
      setLogs(prev => [...prev, '[System] Error: Failed to connect to server. Check backend logs.']);
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = async (runId: string) => {
    try {
      const res = await fetch(`/api/status/${runId}`);
      const data: BookResult = await res.json();
      setCurrentBook(data);
      
      // Update logs (generating log lines based on status)
      const newLogs = [...logs];
      const statusLine = `[System] Current Status: ${data.status.replace(/_/g, ' ').toUpperCase()}`;
      if (!newLogs.includes(statusLine)) {
        newLogs.push(statusLine);
      }
      
      // Add agent activity summary
      data.chapters.forEach(ch => {
        if (ch.status !== 'pending') {
          const chLine = `[Chapter ${ch.chapter_number}] State: ${ch.status.toUpperCase()} (${ch.word_count} words written)`;
          if (!newLogs.includes(chLine)) {
            newLogs.push(chLine);
          }
        }
      });
      
      if (data.status === 'complete') {
        const compLine1 = `[System] PDF Book generated successfully!`;
        const compLine2 = `[System] DOCX Book generated successfully!`;
        if (!newLogs.includes(compLine1)) newLogs.push(compLine1);
        if (!newLogs.includes(compLine2)) newLogs.push(compLine2);
        fetchBooks();
        fetchEvals(runId);
      }
      
      setLogs(newLogs);
      // Cache logs per run ID
      localStorage.setItem(`aiuthor_logs_${runId}`, JSON.stringify(newLogs));
    } catch (e) {
      console.error("Error polling status:", e);
    }
  };

  const fetchEvals = async (runId: string) => {
    try {
      const res = await fetch(`/api/evals/${runId}`);
      if (res.ok) {
        const data = await res.json();
        setEvalReport(data);
        // Cache evals per run ID
        localStorage.setItem(`aiuthor_eval_${runId}`, JSON.stringify(data));
      }
    } catch (e) {
      console.error("Error loading evals:", e);
    }
  };

  const insertChapter = async () => {
    if (!currentBook) return;
    setLoading(true);
    setLogs(prev => [...prev, `[System] Triggering Test Case D insertion...`, `[System] Re-arranging chapters and shifting downstream...`]);
    try {
      const res = await fetch(`/api/insert-chapter/${currentBook.run_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...insertRequest, api_key: apiKey })
      });
      const data = await res.json();
      setCurrentBook(data);
      setLogs(prev => [...prev, `[System] Self-Healing: Downstream repair running in background...`]);
    } catch (e) {
      console.error("Error inserting chapter:", e);
    } finally {
      setLoading(false);
    }
  };

  const selectExistingBook = (book: BookResult) => {
    setCurrentBook(book);
    setCurrentRunId(book.run_id);
    
    // Load cached logs for this run if they exist
    const cachedLogs = localStorage.getItem(`aiuthor_logs_${book.run_id}`);
    if (cachedLogs) {
      setLogs(JSON.parse(cachedLogs));
    } else {
      setLogs([`[System] Loaded book: ${book.outline?.title}`]);
    }
    
    // Load cached evals for this run if they exist
    const cachedEvals = localStorage.getItem(`aiuthor_eval_${book.run_id}`);
    if (cachedEvals) {
      setEvalReport(JSON.parse(cachedEvals));
    } else {
      setEvalReport(null);
    }
    
    if (book.status === 'complete') {
      fetchEvals(book.run_id);
    }
    setActiveTab('monitor');
  };

  // Helper arrays for visualizer
  const agentNodes = [
    { name: 'Planner', description: 'Draws Book Outline', key: 'outline_planned' },
    { name: 'Researcher', description: 'RAG & Web Fetcher', key: 'researching' },
    { name: 'Writer', description: 'Narrative Draft Writer', key: 'writing' },
    { name: 'Humanizer', description: 'Removes tells, DPO openings', key: 'humanizing' },
    { name: 'Editor', description: 'Transitions & Grammar Editor', key: 'editing' },
    { name: 'Fact-Checker', description: 'Citation-or-soften guardrail', key: 'checking' },
    { name: 'Memory Keeper', description: 'Updates registries', key: 'complete' },
    { name: 'Assembler', description: 'Compiles Front/Back matter', key: 'assembling' }
  ];

  const getAgentNodeStatus = (nodeKey: string) => {
    if (!currentBook) return 'pending';
    const status = currentBook.status;
    
    if (status === 'complete') return 'complete';
    if (status === 'failed') return 'failed';
    
    // Check which agent is currently active based on status string
    if (status.includes(nodeKey)) return 'active';
    if (status === 'assembling' && nodeKey === 'assembling') return 'active';
    if (status === 'outline_planned' && nodeKey === 'outline_planned') return 'complete';
    
    // Check chapter pipeline active
    const activeChapter = currentBook.chapters.find(c => c.status !== 'complete' && c.status !== 'pending');
    if (activeChapter) {
      if (activeChapter.status === nodeKey) return 'active';
      // If the active status is after this node key, mark complete
      const statuses = ['researching', 'writing', 'humanizing', 'editing', 'checking'];
      const activeIdx = statuses.indexOf(activeChapter.status);
      const nodeIdx = statuses.indexOf(nodeKey);
      if (nodeIdx !== -1 && activeIdx > nodeIdx) return 'complete';
    }
    
    // Default complete if book is assembled and this was chapter phase
    if (status === 'assembling' && ['outline_planned', 'researching', 'writing', 'humanizing', 'editing', 'checking', 'complete'].includes(nodeKey)) {
      return 'complete';
    }
    
    return 'pending';
  };

  // Calculate totals for token cost ledger
  const totalCost = currentBook?.trace_bundle?.total_cost || 0;
  const totalTokens = currentBook?.trace_bundle?.total_tokens || 0;

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="logo-section">
          <h1>AIuthor <span className="logo-badge">AGENT SYSTEM v1.1</span></h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Publication-Ready Agentic Book Writer
            <span style={{ marginLeft: '1rem', padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, background: apiKey ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)', color: apiKey ? '#10b981' : '#f59e0b', border: apiKey ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(245, 158, 11, 0.4)' }}>
              {apiKey ? '🚀 LIVE OPENAI ACTIVE' : '💡 OFFLINE MOCK MODE'}
            </span>
          </p>
        </div>
        
        <div className="tabs-container">
          <button className={`tab-btn ${activeTab === 'setup' ? 'active' : ''}`} onClick={() => setActiveTab('setup')}>
            <Settings size={18} /> Setup
          </button>
          <button className={`tab-btn ${activeTab === 'monitor' ? 'active' : ''}`} onClick={() => setActiveTab('monitor')}>
            <Sparkles size={18} /> Orchestrator
          </button>
          <button className={`tab-btn ${activeTab === 'memory' ? 'active' : ''}`} onClick={() => setActiveTab('memory')}>
            <Database size={18} /> Memory Bible
          </button>
          <button className={`tab-btn ${activeTab === 'evals' ? 'active' : ''}`} onClick={() => setActiveTab('evals')}>
            <FileSpreadsheet size={18} /> Evals Report
          </button>
          <button className={`tab-btn ${activeTab === 'reader' ? 'active' : ''}`} onClick={() => setActiveTab('reader')}>
            <BookOpen size={18} /> Read Book
          </button>
        </div>
      </header>

      {/* 1. SETUP TAB */}
      {activeTab === 'setup' && (
        <div className="dashboard-grid" style={{ gridTemplateColumns: '2fr 1fr' }}>
          <div className="glow-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>Start New Book Generation</h2>
              <span className={`badge ${apiKey ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}>
                {apiKey ? 'Live OpenAI Mode' : 'Simulated Mock Mode'}
              </span>
            </div>
            
            {apiKey ? (
              <div style={{ padding: '0.75rem', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)', fontSize: '0.85rem' }}>
                <strong>🚀 Live OpenAI Mode Active</strong>: The agentic pipeline will run using your provided API key. Ensure you have sufficient credit limits on OpenAI.
              </div>
            ) : (
              <div style={{ padding: '0.75rem', borderRadius: '6px', background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.2)', fontSize: '0.85rem' }}>
                <strong>💡 Offline Mock Mode Active</strong>: No OpenAI API key is provided. The system will simulate the agents, generating a realistic structured book on your topic instantly.
              </div>
            )}
            
            <div className="form-group">
              <label>Topic / Book Prompt</label>
              <input 
                type="text" 
                className="input-field" 
                value={brief.topic}
                onChange={e => setBrief({...brief, topic: e.target.value})}
              />
            </div>

            <div className="form-group">
              <label>Target Reader Profile</label>
              <textarea 
                rows={3}
                className="input-field" 
                value={brief.reader_profile}
                onChange={e => setBrief({...brief, reader_profile: e.target.value})}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label>Tonality Preset</label>
                <select 
                  className="input-field" 
                  value={brief.tonality}
                  onChange={e => setBrief({...brief, tonality: e.target.value})}
                >
                  <option>Conversational</option>
                  <option>Academic</option>
                  <option>Storyteller</option>
                  <option>Motivational</option>
                  <option>Witty</option>
                </select>
              </div>

              <div className="form-group">
                <label>Target word length</label>
                <input 
                  type="number" 
                  className="input-field" 
                  value={brief.target_words}
                  onChange={e => setBrief({...brief, target_words: parseInt(e.target.value)})}
                />
              </div>

              <div className="form-group">
                <label>Genre</label>
                <select 
                  className="input-field" 
                  value={brief.genre}
                  onChange={e => setBrief({...brief, genre: e.target.value})}
                >
                  <option>Non-Fiction</option>
                  <option>Fiction</option>
                  <option>Technical</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label>Additional Custom Guidelines</label>
              <textarea 
                rows={3}
                className="input-field" 
                value={brief.additional_guidelines}
                onChange={e => setBrief({...brief, additional_guidelines: e.target.value})}
              />
            </div>

            <div className="form-group">
              <label>OpenAI API Key (Optional if configured in backend .env)</label>
              <input 
                type="password" 
                placeholder="sk-..." 
                className="input-field" 
                value={apiKey} 
                onChange={e => setApiKey(e.target.value)} 
              />
            </div>

            <button 
              className="btn-primary" 
              onClick={startGeneration} 
              style={{ width: 'fit-content', marginTop: '1rem' }}
              disabled={loading}
            >
              <Play size={18} /> {loading ? 'Initializing...' : 'Assemble Agent Pipeline & Write'}
            </button>
          </div>

          <div className="sidebar-panel">
            <div className="glow-card">
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '1rem' }}>Active / Completed Runs</h3>
              {bookList.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>No book runs found in workspace.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {bookList.map((b) => (
                    <div 
                      key={b.run_id} 
                      className="glow-card" 
                      style={{ padding: '0.75rem', cursor: 'pointer', border: b.run_id === currentBook?.run_id ? '1px solid var(--primary)' : '1px solid transparent', background: 'rgba(0,0,0,0.1)' }}
                      onClick={() => selectExistingBook(b)}
                    >
                      <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>{b.outline?.title || 'Untitled Book'}</h4>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>ID: {b.run_id} | Status: <span className="badge badge-success">{b.status}</span></p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <div className="glow-card">
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '0.5rem' }}>Evaluation Rubrics</h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                This dashboard tracks structural completeness, RAG lookup accuracy, and removes standard AI tells. Ensure your GEMINI_API_KEY is configured in the environment.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 2. MONITOR TAB */}
      {activeTab === 'monitor' && (
        <div className="dashboard-grid">
          {/* Agent Visualizer */}
          <div className="sidebar-panel">
            <div className="glow-card orchestrator-box">
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', borderBottom: '1px solid var(--panel-border)', paddingBottom: '0.5rem' }}>Agent Visualizer</h3>
              
              <div className="node-list">
                {agentNodes.map((node) => {
                  const status = getAgentNodeStatus(node.key);
                  return (
                    <div key={node.name} className={`node-item ${status}`}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          {node.name} 
                          {status === 'active' && <RotateCw size={14} className="spin" style={{ color: 'var(--primary)' }} />}
                          {status === 'complete' && <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{node.description}</div>
                      </div>
                      <span className={`badge badge-${status === 'active' ? 'primary' : status === 'complete' ? 'success' : 'warning'}`}>
                        {status.toUpperCase()}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Token ledger */}
            <div className="glow-card">
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <DollarSign size={18} /> Cost & Token Ledger
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Total Tokens:</span>
                  <span style={{ fontWeight: 600 }}>{totalTokens.toLocaleString()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.5rem' }}>
                  <span>Estimated Cost:</span>
                  <span style={{ fontWeight: 600, color: 'var(--success)' }}>${totalCost.toFixed(6)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Book Title & Chapter Progress */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="glow-card">
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.6rem' }}>
                {currentBook?.outline?.title || 'Drafting Outlines...'}
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
                {currentBook?.outline?.subtitle || 'Generating subtitles...'}
              </p>
              
              <div style={{ display: 'flex', gap: '1.5rem', marginTop: '1.2rem', fontSize: '0.9rem' }}>
                <div>Run ID: <span style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>{currentBook?.run_id || 'N/A'}</span></div>
                <div>Status: <span className="badge badge-primary">{(currentBook?.status || 'IDLE').toUpperCase()}</span></div>
                <div>Chapters written: <span>{currentBook?.chapters.filter(c => c.status === 'complete').length || 0} / {currentBook?.chapters.length || 0}</span></div>
              </div>
            </div>

            {/* real-time logs */}
            <div className="glow-card">
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '0.75rem' }}>Execution Logs</h3>
              <div className="log-box">
                {logs.map((log, i) => (
                  <div key={i} className="log-entry">{log}</div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>

            {/* Traces */}
            <div className="glow-card">
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Layers size={18} /> Observability: Detailed Traces
              </h3>
              {currentBook?.trace_bundle?.traces && currentBook.trace_bundle.traces.length > 0 ? (
                <div>
                  {currentBook.trace_bundle.traces.map((trace, idx) => (
                    <div key={idx} className="trace-card">
                      <div className="trace-header" onClick={() => setExpandedTraceIdx(expandedTraceIdx === idx ? null : idx)}>
                        <span style={{ fontWeight: 600 }}>{trace.agent_name} - {trace.step_name}</span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{trace.timestamp.split('T')[1].split('.')[0]}</span>
                      </div>
                      {expandedTraceIdx === idx && (
                        <div className="trace-content">
                          <strong>Input:</strong>
                          <pre>{JSON.stringify(trace.input_data, null, 2)}</pre>
                          <strong style={{ display: 'block', marginTop: '1rem' }}>Output:</strong>
                          <pre>{typeof trace.output_data === 'string' ? trace.output_data : JSON.stringify(trace.output_data, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: 'var(--text-muted)' }}>No detailed agent traces recorded yet for this run.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 3. MEMORY BIBLE TAB */}
      {activeTab === 'memory' && (
        <div className="glow-card">
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.6rem', marginBottom: '1.5rem' }}>Cross-Chapter Memory Bible</h2>
          
          <div className="tabs-container" style={{ marginBottom: '1.5rem' }}>
            <button className={`tab-btn ${memorySubTab === 'facts' ? 'active' : ''}`} onClick={() => setMemorySubTab('facts')}>
              Fact Registry
            </button>
            <button className={`tab-btn ${memorySubTab === 'concepts' ? 'active' : ''}`} onClick={() => setMemorySubTab('concepts')}>
              Concept Bible
            </button>
            <button className={`tab-btn ${memorySubTab === 'callbacks' ? 'active' : ''}`} onClick={() => setMemorySubTab('callbacks')}>
              Callback Index
            </button>
            <button className={`tab-btn ${memorySubTab === 'decisions' ? 'active' : ''}`} onClick={() => setMemorySubTab('decisions')}>
              Decision Log
            </button>
          </div>

          {/* Sub-tab content */}
          {memorySubTab === 'facts' && (
            <div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.95rem' }}>
                Extracted facts that have been cross-checked by the Fact-Checker agent to prevent hallucinations in future chapters.
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--panel-border)', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    <th style={{ padding: '0.75rem' }}>Factual Claim</th>
                    <th style={{ padding: '0.75rem' }}>Source Chapter</th>
                    <th style={{ padding: '0.75rem' }}>Verified</th>
                    <th style={{ padding: '0.75rem' }}>Citations</th>
                  </tr>
                </thead>
                <tbody>
                  {currentBook?.memories.fact_registry && currentBook.memories.fact_registry.length > 0 ? (
                    currentBook.memories.fact_registry.map((fact, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <td style={{ padding: '0.75rem' }}>{fact.claim}</td>
                        <td style={{ padding: '0.75rem' }}>Chapter {fact.source_chapter}</td>
                        <td style={{ padding: '0.75rem' }}><span className="badge badge-success">VERIFIED</span></td>
                        <td style={{ padding: '0.75rem' }}>{fact.citation || 'Grounded doc'}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No facts stored yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {memorySubTab === 'concepts' && (
            <div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.95rem' }}>
                The core dictionary of terms, character profiles, or organizations defined so they are named and used consistently.
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--panel-border)', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    <th style={{ padding: '0.75rem' }}>Concept / Character</th>
                    <th style={{ padding: '0.75rem' }}>Type</th>
                    <th style={{ padding: '0.75rem' }}>Description</th>
                    <th style={{ padding: '0.75rem' }}>First Introduced</th>
                  </tr>
                </thead>
                <tbody>
                  {currentBook?.memories.concept_bible && currentBook.memories.concept_bible.length > 0 ? (
                    currentBook.memories.concept_bible.map((concept, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 600 }}>{concept.name}</td>
                        <td style={{ padding: '0.75rem' }}><span className="badge badge-primary">{concept.type.toUpperCase()}</span></td>
                        <td style={{ padding: '0.75rem' }}>{concept.description}</td>
                        <td style={{ padding: '0.75rem' }}>Chapter {concept.first_introduced_chapter}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No concepts defined yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {memorySubTab === 'callbacks' && (
            <div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.95rem' }}>
                Callbacks index containing milestones, incidents or character callbacks that have been flagged to be mentioned in subsequent chapters.
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--panel-border)', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    <th style={{ padding: '0.75rem' }}>Callback Content</th>
                    <th style={{ padding: '0.75rem' }}>Source Chapter</th>
                    <th style={{ padding: '0.75rem' }}>Target Chapter</th>
                    <th style={{ padding: '0.75rem' }}>Trigger Condition</th>
                  </tr>
                </thead>
                <tbody>
                  {currentBook?.memories.callback_index && currentBook.memories.callback_index.length > 0 ? (
                    currentBook.memories.callback_index.map((callback, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <td style={{ padding: '0.75rem' }}>{callback.content}</td>
                        <td style={{ padding: '0.75rem' }}>Chapter {callback.source_chapter}</td>
                        <td style={{ padding: '0.75rem' }}>{callback.target_chapter ? `Chapter ${callback.target_chapter}` : 'Natural'}</td>
                        <td style={{ padding: '0.75rem' }}>{callback.callback_trigger}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No callback milestones logged.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {memorySubTab === 'decisions' && (
            <div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.95rem' }}>
                A ledger of creative and structural choices made by the agents throughout the writing process, providing an audit trail.
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--panel-border)', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    <th style={{ padding: '0.75rem' }}>Creative Decision</th>
                    <th style={{ padding: '0.75rem' }}>Context</th>
                    <th style={{ padding: '0.75rem' }}>Rationale</th>
                    <th style={{ padding: '0.75rem' }}>Agent / Chapter</th>
                  </tr>
                </thead>
                <tbody>
                  {currentBook?.memories.decision_log && currentBook.memories.decision_log.length > 0 ? (
                    currentBook.memories.decision_log.map((decision, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 500 }}>{decision.decision}</td>
                        <td style={{ padding: '0.75rem' }}>{decision.context}</td>
                        <td style={{ padding: '0.75rem' }}>{decision.rationale}</td>
                        <td style={{ padding: '0.75rem' }}>{decision.agent} | Ch. {decision.chapter_number}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No decisions recorded.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 4. EVALS TAB */}
      {activeTab === 'evals' && (
        <div className="glow-card">
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.6rem', marginBottom: '1.5rem' }}>Automated Quality Evaluation Report</h2>
          {evalReport ? (
            <div>
              <div className="score-grid">
                <div className="score-card">
                  <h4>Overall Score</h4>
                  <div className="score-value">{(evalReport.overall_score * 100).toFixed(0)}%</div>
                  <span className="badge badge-success">OUTSTANDING</span>
                </div>
                <div className="score-card">
                  <h4>Completeness</h4>
                  <div className="score-value">{(evalReport.completeness.score * 100).toFixed(0)}%</div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{evalReport.completeness.feedback}</p>
                </div>
                <div className="score-card">
                  <h4>Tonality Fidelity</h4>
                  <div className="score-value">{(evalReport.tonality.score * 100).toFixed(0)}%</div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{evalReport.tonality.feedback}</p>
                </div>
                <div className="score-card">
                  <h4>AI Tells Detection</h4>
                  <div className="score-value">{(evalReport.ai_tells.score * 100).toFixed(0)}%</div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{evalReport.ai_tells.feedback}</p>
                </div>
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '2rem' }}>
                <div className="glow-card" style={{ background: 'rgba(0,0,0,0.1)' }}>
                  <h4 style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Fact Coverage Metric</h4>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>{evalReport.fact_coverage.feedback}</p>
                </div>
                <div className="glow-card" style={{ background: 'rgba(0,0,0,0.1)' }}>
                  <h4 style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Callback Recall Metric</h4>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>{evalReport.callback_recall.feedback}</p>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              <AlertCircle size={32} style={{ display: 'block', margin: '0 auto 1rem auto' }} />
              <p style={{ textAlign: 'center' }}>No evaluations loaded. Generate a book or select a completed book to view the quality evaluation report.</p>
            </div>
          )}
        </div>
      )}

      {/* 5. READER TAB */}
      {activeTab === 'reader' && (
        <div className="glow-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--panel-border)', paddingBottom: '1rem' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.6rem' }}>Book Reader & Repair Console</h2>
            
            {currentBook && currentBook.status === 'complete' && (
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <a href={`/api/books/download/${currentBook.run_id}/pdf`} target="_blank" rel="noreferrer" className="btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}>
                  <Download size={16} /> Download PDF
                </a>
                <a href={`/api/books/download/${currentBook.run_id}/docx`} className="btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem', background: '#3b82f6', boxShadow: 'none' }}>
                  <Download size={16} /> Download Word (DOCX)
                </a>
              </div>
            )}
          </div>

          {currentBook ? (
            <div className="book-reader">
              <div className="reader-sidebar">
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>Front Matter</h4>
                <div className={`toc-item ${activeChapterIndex === -1 ? 'active' : ''}`} onClick={() => setActiveChapterIndex(-1)}>
                  Title & Front Matter
                </div>
                
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '1rem', marginBottom: '0.5rem' }}>Chapters</h4>
                {currentBook.chapters.map((ch, idx) => (
                  <div 
                    key={ch.chapter_number}
                    className={`toc-item ${activeChapterIndex === idx ? 'active' : ''}`}
                    onClick={() => setActiveChapterIndex(idx)}
                  >
                    Chapter {ch.chapter_number}: {ch.title}
                  </div>
                ))}

                {/* Test Case D Insertion Trigger inside Sidebar */}
                {currentBook.status === 'complete' && (
                  <div style={{ borderTop: '1px solid var(--panel-border)', marginTop: '2rem', paddingTop: '1rem' }}>
                    <h4 style={{ fontSize: '0.85rem', color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <PlusCircle size={14} /> Self-Healing Test D
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div className="form-group">
                        <label style={{ fontSize: '0.75rem' }}>Insert After Chapter</label>
                        <select 
                          className="input-field" 
                          style={{ padding: '0.35rem', fontSize: '0.85rem' }}
                          value={insertRequest.insert_after_chapter}
                          onChange={e => setInsertRequest({...insertRequest, insert_after_chapter: parseInt(e.target.value)})}
                        >
                          {currentBook.chapters.map(c => (
                            <option key={c.chapter_number} value={c.chapter_number}>Chapter {c.chapter_number}</option>
                          ))}
                        </select>
                      </div>
                      
                      <div className="form-group">
                        <label style={{ fontSize: '0.75rem' }}>Chapter Title</label>
                        <input 
                          type="text" 
                          className="input-field" 
                          style={{ padding: '0.35rem', fontSize: '0.85rem' }} 
                          value={insertRequest.title}
                          onChange={e => setInsertRequest({...insertRequest, title: e.target.value})}
                        />
                      </div>
                      
                      <button 
                        className="btn-primary" 
                        style={{ padding: '0.4rem', fontSize: '0.85rem', background: 'var(--accent)', boxShadow: '0 0 10px var(--accent-glow)' }}
                        onClick={insertChapter}
                        disabled={loading}
                      >
                        {loading ? 'Repairing...' : 'Insert & Heal Downstream'}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Reader panel */}
              <div className="reader-content">
                {activeChapterIndex === -1 ? (
                  <div>
                    <h2>Title & Front Matter</h2>
                    <p style={{ whiteSpace: 'pre-wrap' }}><strong>Half Title:</strong> {currentBook.outline?.title}</p>
                    <p style={{ whiteSpace: 'pre-wrap', marginTop: '1rem' }}><strong>Author:</strong> {currentBook.outline?.author}</p>
                  </div>
                ) : (
                  <div>
                    {currentBook.chapters[activeChapterIndex] ? (
                      <div>
                        <h2>Chapter {currentBook.chapters[activeChapterIndex].chapter_number}: {currentBook.chapters[activeChapterIndex].title}</h2>
                        
                        {/* Word Count */}
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1.2rem' }}>
                          Word Count: {currentBook.chapters[activeChapterIndex].word_count || 0} words
                        </div>
                        
                        {/* Content text */}
                        <div style={{ whiteSpace: 'pre-wrap' }}>
                          {currentBook.chapters[activeChapterIndex].final_text ? (
                            currentBook.chapters[activeChapterIndex].final_text
                          ) : (
                            <div style={{ color: 'var(--text-muted)' }}>
                              Draft pending. Status: <span className="badge badge-warning">{currentBook.chapters[activeChapterIndex].status}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p style={{ color: 'var(--text-muted)' }}>Select a chapter to read.</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '3rem' }}>Please select or generate a book to view content.</p>
          )}
        </div>
      )}
    </div>
  );
}
