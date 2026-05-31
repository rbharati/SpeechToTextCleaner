import { useMemo, useRef, useState, useEffect } from 'react';

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<{
    0: {
      transcript: string;
    };
  }>;
};

type MetricInfo = {
  score: number;
  reasons: string[];
};

type FluencyInfo = {
  perplexity: number;
  confidence: string;
};

type PipelineStep = {
  raw: string;
  normalized: string;
  grammar_corrected: string;
  spoken_grammar: { text: string; changed: boolean };
  corrected: string;
  confidence: MetricInfo;
  fluency: FluencyInfo;
  semantic_word_choice: { text: string; changed: boolean; fluency?: FluencyInfo };
  llm: {
    allowed: boolean;
    forced: boolean;
    used: boolean;
    needed: boolean;
    reasons: string[];
    text?: string;
    usage?: { input_tokens: number; output_tokens: number; total_tokens: number; cost_usd: number };
  };
  latencies: Record<string, number>;
};

type ComparisonResult = {
  raw: string;
  library_only: {
    text: string;
    latency_ms: number;
    confidence: MetricInfo;
    fluency: FluencyInfo;
    llm_used: boolean;
    tokens: number;
    cost_usd: number;
    pipeline_detail: PipelineStep;
  };
  llm_only: {
    text: string;
    latency_ms: number;
    confidence: MetricInfo;
    fluency: FluencyInfo;
    llm_used: boolean;
    tokens: number;
    cost_usd: number;
  };
  hybrid: {
    text: string;
    latency_ms: number;
    confidence: MetricInfo;
    fluency: FluencyInfo;
    llm_used: boolean;
    llm_needed: boolean;
    llm_reasons: string[];
    tokens: number;
    cost_usd: number;
    saved_by_libraries: boolean;
    pipeline_detail: PipelineStep;
  };
};

type CumulativeStats = {
  totalRuns: number;
  bypassedCount: number;
  totalCostSaved: number;
  totalLatencySaved: number;
};

declare global {
  interface Window {
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

const PRESETS = [
  {
    label: "Linguistic Fillers",
    subtitle: "Local normalizer & repair",
    text: "uh, so like, basically my name John and I am study class 10 and, um, going to share it",
    icon: "🗣️",
  },
  {
    label: "Homophone Confusions",
    subtitle: "Local semantic fixes",
    text: "I want to hear their voice and see if there going to the meet to buy some meat.",
    icon: "🔊",
  },
  {
    label: "Standard Grammar Slip",
    subtitle: "Local GEC Model GEC",
    text: "He do not has any books because he lose them yesterday.",
    icon: "📝",
  },
  {
    label: "Severe Syntax Errors",
    subtitle: "Triggers LLM fallback",
    text: "yesterday went i to store and i buy some stuff and it was very good because it is blue and i study class 10",
    icon: "🚨",
  },
  {
    label: "Already Perfect Speech",
    subtitle: "Fully bypassed (no LLM)",
    text: "The weather today is absolutely beautiful and perfect for a walk in the park.",
    icon: "✨",
  },
];

function App() {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const recordingBaseRef = useRef('');

  const [rawText, setRawText] = useState('');
  const [compareResult, setCompareResult] = useState<ComparisonResult | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isCorrecting, setIsCorrecting] = useState(false);
  const [message, setMessage] = useState('');

  // Settings
  const [confidenceThreshold, setConfidenceThreshold] = useState(75);
  const [selectedPresetIndex, setSelectedPresetIndex] = useState<number | null>(null);

  // Cumulative Stats loaded from localStorage
  const [stats, setStats] = useState<CumulativeStats>(() => {
    try {
      const saved = localStorage.getItem('speech_cleaner_stats');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {
      // Ignore parsing errors
    }
    return {
      totalRuns: 0,
      bypassedCount: 0,
      totalCostSaved: 0,
      totalLatencySaved: 0,
    };
  });

  useEffect(() => {
    localStorage.setItem('speech_cleaner_stats', JSON.stringify(stats));
  }, [stats]);

  const hasSpeechApi = typeof window.webkitSpeechRecognition !== 'undefined';
  const isSecure = window.isSecureContext;
  const speechSupported = hasSpeechApi && isSecure;

  const statusLabel = useMemo(() => {
    if (!speechSupported) return 'Manual mode';
    if (isListening) return 'Listening';
    if (isCorrecting) return 'Correcting';
    return 'Ready';
  }, [isCorrecting, isListening, speechSupported]);

  const initialNotice = useMemo(() => {
    if (speechSupported) return '';

    if (hasSpeechApi) {
      return 'Microphone needs HTTPS on WiFi. Open this app with https:// and accept the local certificate.';
    }

    return 'Speech recognition is not available in this browser. Try Chrome or Edge, or type manually.';
  }, [hasSpeechApi, speechSupported]);

  function getRecognition() {
    if (!speechSupported || !window.webkitSpeechRecognition) {
      setMessage(initialNotice);
      return null;
    }

    if (recognitionRef.current) {
      return recognitionRef.current;
    }

    const recognition = new window.webkitSpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let sessionTranscript = '';

      for (let i = 0; i < event.results.length; i += 1) {
        sessionTranscript += event.results[i][0].transcript;
      }

      const nextText = [recordingBaseRef.current, sessionTranscript]
        .map((part) => part.trim())
        .filter(Boolean)
        .join(' ');

      setRawText(nextText);
      setSelectedPresetIndex(null);
    };

    recognition.onend = () => {
      setIsListening((current) => {
        if (current) {
          try {
            recognition.start();
          } catch {
            return false;
          }
        }

        return current;
      });
    };

    recognition.onerror = (event) => {
      setIsListening(false);

      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setMessage('Microphone permission was blocked. Allow microphone access in browser site settings.');
        return;
      }

      setMessage('Speech recognition stopped. Try again or type manually.');
    };

    recognitionRef.current = recognition;
    return recognition;
  }

  function toggleListening() {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const recognition = getRecognition();
    if (!recognition) return;

    try {
      setMessage('');
      setIsListening(true);
      recordingBaseRef.current = rawText.trim();
      recognition.start();
    } catch {
      setIsListening(false);
      setMessage('Could not start the microphone. Check permission and try again.');
    }
  }

  async function handleCorrect(text = rawText) {
    const cleanText = text.trim();
    if (!cleanText || isCorrecting) return;

    setIsCorrecting(true);
    setMessage('');

    try {
      const response = await fetch('/compare', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: cleanText,
          confidence_threshold: confidenceThreshold,
        }),
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const data = (await response.json()) as ComparisonResult;
      setCompareResult(data);

      // Accumulate Statistics to PROVE Hypothesis!
      const costSaved = Math.max(0, data.llm_only.cost_usd - data.hybrid.cost_usd);
      const latencySaved = Math.max(0, (data.llm_only.latency_ms - data.hybrid.latency_ms) / 1000);

      setStats((prev) => ({
        totalRuns: prev.totalRuns + 1,
        bypassedCount: prev.bypassedCount + (data.hybrid.saved_by_libraries ? 1 : 0),
        totalCostSaved: prev.totalCostSaved + costSaved,
        totalLatencySaved: prev.totalLatencySaved + latencySaved,
      }));
    } catch (e) {
      console.error(e);
      setMessage('Unable to reach the correction API. Keep Flask running on port 5000.');
    } finally {
      setIsCorrecting(false);
    }
  }

  function selectPreset(index: number) {
    setSelectedPresetIndex(index);
    setRawText(PRESETS[index].text);
    setMessage('');
  }

  function clearAll() {
    recordingBaseRef.current = '';
    setRawText('');
    setCompareResult(null);
    setSelectedPresetIndex(null);
    setMessage(initialNotice);
  }

  function resetStats() {
    setStats({
      totalRuns: 0,
      bypassedCount: 0,
      totalCostSaved: 0,
      totalLatencySaved: 0,
    });
  }

  async function copyToClipboard(text: string) {
    if (!text || !navigator.clipboard) return;
    await navigator.clipboard.writeText(text);
  }

  // Calculate session percentage of LLM bypass
  const bypassRate = stats.totalRuns > 0 ? Math.round((stats.bypassedCount / stats.totalRuns) * 100) : 0;

  // Active detail pipeline for stepping workflow
  const activePipeline = compareResult?.hybrid.pipeline_detail;

  return (
    <main className="app-shell">
      <div className="dashboard-grid">
        
        {/* LEFT COLUMN: Input, Settings & Stats */}
        <section className="left-panel">
          <header className="app-header glass">
            <div>
              <p className="eyebrow">Speech to text With correction</p>
              <h1>LLM as Last Resort</h1>
              <p className="subtitle">Speech Correction Pipeline</p>
            </div>

            <div className={`status-pill ${isListening ? 'active' : ''}`}>
              <span className="status-dot" />
              {statusLabel}
            </div>
          </header>

          {/* 1. Presets playground */}
          <section className="card surface">
            <h3 className="section-title">🧪 Select a Speech Error Case</h3>
            <div className="preset-list">
              {PRESETS.map((preset, idx) => (
                <button
                  key={idx}
                  className={`preset-item ${selectedPresetIndex === idx ? 'active' : ''}`}
                  onClick={() => selectPreset(idx)}
                >
                  <span className="preset-icon">{preset.icon}</span>
                  <div className="preset-info">
                    <span className="preset-title">{preset.label}</span>
                    <span className="preset-desc">{preset.subtitle}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* 2. Audio Composer */}
          <section className="card surface composer">
            <label htmlFor="speech-input" className="label-row">
              <span>Your Speech Transcript</span>
              {rawText && <span className="char-count">{rawText.length} chars</span>}
            </label>
            <textarea
              id="speech-input"
              value={rawText}
              onChange={(e) => {
                setRawText(e.target.value);
                setSelectedPresetIndex(null);
              }}
              placeholder="Record your voice, click a preset case above, or type manually..."
              rows={4}
            />

            <div className="action-bar">
              <button
                className="mic-button"
                type="button"
                onClick={toggleListening}
                disabled={!speechSupported}
                aria-pressed={isListening}
              >
                <span className="mic-glyph" />
                {isListening ? 'Stop' : 'Record'}
              </button>

              <button
                className="primary-button"
                type="button"
                onClick={() => handleCorrect()}
                disabled={!rawText.trim() || isCorrecting}
              >
                {isCorrecting ? 'Processing Pipeline...' : 'Run Pipeline'}
              </button>

              <button
                className="clear-button"
                type="button"
                onClick={clearAll}
                disabled={!rawText && !compareResult}
              >
                Clear
              </button>
            </div>

            {(message || initialNotice) && (
              <p className="notice">{message || initialNotice}</p>
            )}
          </section>

          {/* 3. Settings controls */}
          <section className="card surface settings-card">
            <h3>⚙️ Pipeline Constraints</h3>
            <div className="setting-row">
              <div className="setting-header">
                <span>Confidence Threshold Gate</span>
                <strong>{confidenceThreshold}%</strong>
              </div>
              <p className="setting-hint">If local libraries score below this, the LLM will be invoked.</p>
              <input
                type="range"
                min="50"
                max="95"
                step="5"
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(parseInt(e.target.value))}
                className="threshold-slider"
              />
            </div>
          </section>

          {/* 4. Session Savings Dashboard */}
          <section className="card surface stats-card">
            <div className="stats-header">
              <h3>📊 Session Proof Dashboard</h3>
              {stats.totalRuns > 0 && (
                <button className="reset-stats-btn" onClick={resetStats}>Reset Stats</button>
              )}
            </div>
            
            <div className="stats-grid">
              <article className="stat-card accent">
                <span>Avoided LLMs</span>
                <strong className={bypassRate > 0 ? "success" : ""}>{bypassRate}%</strong>
                <small>{stats.bypassedCount} of {stats.totalRuns} runs resolved locally</small>
              </article>
              <article className="stat-card">
                <span>Total Cost Saved</span>
                <strong>${stats.totalCostSaved.toFixed(5)}</strong>
                <small>USD saved vs Direct LLM</small>
              </article>
              <article className="stat-card">
                <span>Latency Saved</span>
                <strong>{stats.totalLatencySaved.toFixed(2)}s</strong>
                <small>Total API waiting time cut</small>
              </article>
            </div>
            
            {stats.totalRuns > 0 && (
              <p className="stats-interpretation">
                🎉 <strong>Hypothesis Verified:</strong> In <strong>{bypassRate}%</strong> of cases, our hybrid pipeline bypassed the heavy LLM entirely, saving <strong>{stats.totalLatencySaved.toFixed(1)}s</strong> of network latency and cutting API bills to zero, while maintaining prime text quality!
              </p>
            )}
          </section>
        </section>

        {/* RIGHT COLUMN: Comparative view & Workflow Stepper */}
        <section className="right-panel">
          
          {compareResult ? (
            <>
              {/* Paradigm Comparisons */}
              <section className="card surface comparison-section">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Side-by-Side Analysis</p>
                    <h2>Architectural Paradigms</h2>
                  </div>
                </div>

                <div className="comparison-cards">
                  
                  {/* Card 1: Library-Only */}
                  <article className="paradigm-card border-blue">
                    <div className="paradigm-badge">Library Only</div>
                    <p className="paradigm-text">"{compareResult.library_only.text}"</p>
                    
                    <div className="paradigm-metrics">
                      <div className="metric-row">
                        <span>Latency</span>
                        <strong>{compareResult.library_only.latency_ms.toFixed(0)} ms</strong>
                      </div>
                      <div className="metric-row">
                        <span>API Cost</span>
                        <strong className="free">$0.00 (FREE)</strong>
                      </div>
                      <div className="metric-row">
                        <span>Quality (PPL)</span>
                        <strong>{compareResult.library_only.fluency.perplexity.toFixed(1)}</strong>
                      </div>
                    </div>
                    <button className="copy-btn" onClick={() => copyToClipboard(compareResult.library_only.text)}>Copy Output</button>
                  </article>

                  {/* Card 2: Direct LLM */}
                  <article className="paradigm-card border-red">
                    <div className="paradigm-badge">Direct LLM Only</div>
                    <p className="paradigm-text">"{compareResult.llm_only.text}"</p>
                    
                    <div className="paradigm-metrics">
                      <div className="metric-row">
                        <span>Latency</span>
                        <strong className="slow">{compareResult.llm_only.latency_ms.toFixed(0)} ms</strong>
                      </div>
                      <div className="metric-row">
                        <span>API Cost</span>
                        <strong className="cost">${compareResult.llm_only.cost_usd.toFixed(6)}</strong>
                      </div>
                      <div className="metric-row">
                        <span>Quality (PPL)</span>
                        <strong>{compareResult.llm_only.fluency.perplexity.toFixed(1)}</strong>
                      </div>
                    </div>
                    <button className="copy-btn" onClick={() => copyToClipboard(compareResult.llm_only.text)}>Copy Output</button>
                  </article>

                  {/* Card 3: Hybrid Pipeline */}
                  <article className="paradigm-card border-green highlighted">
                    <div className="paradigm-badge green">Hybrid Pipeline (Ours)</div>
                    <p className="paradigm-text">"{compareResult.hybrid.text}"</p>
                    
                    {compareResult.hybrid.saved_by_libraries ? (
                      <div className="bypass-tag success">⚡ Bypassed LLM (100% savings!)</div>
                    ) : (
                      <div className="bypass-tag trigger">🤖 LLM Invoked (Local scored below {confidenceThreshold}%)</div>
                    )}

                    <div className="paradigm-metrics">
                      <div className="metric-row">
                        <span>Latency</span>
                        <strong className="fast">{compareResult.hybrid.latency_ms.toFixed(0)} ms</strong>
                      </div>
                      <div className="metric-row">
                        <span>API Cost</span>
                        <strong className={compareResult.hybrid.cost_usd > 0 ? "cost" : "free"}>
                          ${compareResult.hybrid.cost_usd.toFixed(6)}
                        </strong>
                      </div>
                      <div className="metric-row">
                        <span>Quality (PPL)</span>
                        <strong>{compareResult.hybrid.fluency.perplexity.toFixed(1)}</strong>
                      </div>
                    </div>
                    <button className="copy-btn primary" onClick={() => copyToClipboard(compareResult.hybrid.text)}>Copy Final Output</button>
                  </article>
                  
                </div>
              </section>

              {/* Step-by-Step Stepper Visualizer */}
              {activePipeline && (
                <section className="card surface stepper-section">
                  <h3>🪜 Multi-Layer Pipeline Stepper</h3>
                  <p className="stepper-desc">Trace exactly how your spoken transcript was cleaned, repaired, and analyzed layer-by-layer.</p>
                  
                  <div className="stepper-timeline">
                    
                    {/* Layer 1: Normalizer */}
                    <div className="step-block active">
                      <div className="step-number">1</div>
                      <div className="step-content">
                        <div className="step-header">
                          <h4>Text Normalizer</h4>
                          <span className="step-latency">{activePipeline.latencies.normalization_ms} ms</span>
                        </div>
                        <p className="step-desc">Removes conversational filler words (uh, um, like), repeated tokens, and fixes basic punctuation.</p>
                        <div className="step-output">"{activePipeline.normalized}"</div>
                      </div>
                    </div>

                    {/* Layer 2: Local GEC Model */}
                    <div className="step-block active">
                      <div className="step-number">2</div>
                      <div className="step-content">
                        <div className="step-header">
                          <h4>Local GEC Model</h4>
                          <span className="step-latency">{activePipeline.latencies.grammar_corrected_ms} ms</span>
                        </div>
                        <p className="step-desc">Applies spelling and grammatical edits using local sequence-to-sequence model.</p>
                        <div className="step-output">"{activePipeline.grammar_corrected}"</div>
                      </div>
                    </div>

                    {/* Layer 3: Spoken Grammar Repair */}
                    <div className="step-block active">
                      <div className="step-number">3</div>
                      <div className="step-content">
                        <div className="step-header">
                          <h4>Spoken Grammar Repair</h4>
                          <span className="step-latency">{activePipeline.latencies.spoken_grammar_ms} ms</span>
                        </div>
                        <p className="step-desc">Corrects speech-specific fragments, missing copulas (be-verbs), tense alignment, and capitalize 'I'.</p>
                        <div className="step-output">"{activePipeline.spoken_grammar.text}"</div>
                      </div>
                    </div>

                    {/* Layer 4: Semantic Homophone Correction */}
                    <div className="step-block active">
                      <div className="step-number">4</div>
                      <div className="step-content">
                        <div className="step-header">
                          <h4>Semantic Confusion Fixer</h4>
                          <span className="step-latency">{activePipeline.latencies.semantic_word_choice_ms} ms</span>
                        </div>
                        <p className="step-desc">Resolves homophones (there/their, meat/meet, by/buy) using spaCy confusion matrices and fluency scores.</p>
                        <div className="step-output">"{activePipeline.semantic_word_choice.text}"</div>
                      </div>
                    </div>

                    {/* Layer 5: Gatekeeping & Assessment */}
                    <div className="step-block active border-dashed">
                      <div className="step-number gate">⚖️</div>
                      <div className="step-content">
                        <div className="step-header">
                          <h4>Pipeline Quality Gatekeeper</h4>
                          <span className="step-latency">{activePipeline.latencies.scoring_ms} ms</span>
                        </div>
                        <p className="step-desc">Calculates quality indicators. Determines whether the text requires high-cost LLM intervention.</p>
                        
                        <div className="gate-metrics">
                          <div className="gate-metric">
                            <span>Confidence Score</span>
                            <strong className={activePipeline.confidence.score >= confidenceThreshold ? "success" : "danger"}>
                              {activePipeline.confidence.score}/100
                            </strong>
                            <small>(Target: &gt;={confidenceThreshold})</small>
                          </div>
                          <div className="gate-metric">
                            <span>Fluency (DistilGPT2)</span>
                            <strong className={activePipeline.fluency.confidence === 'HIGH' ? "success" : activePipeline.fluency.confidence === 'MEDIUM' ? "warning" : "danger"}>
                              {activePipeline.fluency.confidence}
                            </strong>
                            <small>(PPL: {activePipeline.fluency.perplexity.toFixed(1)})</small>
                          </div>
                        </div>

                        {activePipeline.llm.needed ? (
                          <div className="gate-decision trigger">
                            <span>⚠️ LLM Fallback Triggered</span>
                            <p><strong>Reasons:</strong> {activePipeline.llm.reasons.join(", ")}</p>
                          </div>
                        ) : (
                          <div className="gate-decision bypass">
                            <span>✅ Bypassed LLM fallback</span>
                            <p>All local criteria met. Output is fully certified!</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Layer 6: LLM Fallback */}
                    <div className={`step-block ${activePipeline.llm.used ? 'active' : 'bypassed'}`}>
                      <div className={`step-number ${activePipeline.llm.used ? 'llm-active' : 'llm-bypass'}`}>
                        {activePipeline.llm.used ? '🤖' : '💤'}
                      </div>
                      <div className="step-content">
                        <div className="step-header">
                          <h4>LLM Last Resort Fallback ({activePipeline.llm.used ? 'gpt-4o-mini' : 'Bypassed'})</h4>
                          <span className="step-latency">{activePipeline.latencies.llm_ms} ms</span>
                        </div>
                        {activePipeline.llm.used ? (
                          <>
                            <p className="step-desc">Polishes complex semantic relationships and guarantees standard natural English output.</p>
                            <div className="step-output">"{activePipeline.corrected}"</div>
                            <div className="step-usage">
                              <span>Tokens: {activePipeline.llm.usage?.total_tokens}</span>
                              <span>Est. Cost: ${activePipeline.llm.usage?.cost_usd.toFixed(6)}</span>
                            </div>
                          </>
                        ) : (
                          <p className="step-desc gray">LLM stayed asleep. Zero tokens used. You saved <strong>${(125 * 0.150 / 1_000_000 + 19 * 0.600 / 1_000_000).toFixed(6)}</strong> and <strong>~1.5s</strong> of network latency!</p>
                        )}
                      </div>
                    </div>

                  </div>
                </section>
              )}
            </>
          ) : (
            <div className="empty-state-container card surface">
              <div className="empty-state-icon">🔬</div>
              <h2>Hypothesis Lab is Idle</h2>
              <p>Speak something or choose one of our <strong>Speech Error Cases</strong> on the left, then click <strong>"Run Pipeline"</strong> to scientifically prove that libraries should come before LLMs.</p>
            </div>
          )}

        </section>
      </div>
    </main>
  );
}

export default App;
