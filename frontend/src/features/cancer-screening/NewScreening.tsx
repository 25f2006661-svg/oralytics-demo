import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import { ArrowRight, ImagePlus, Plus, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../../services/api';
import type { DemoScenario, ScreeningAnalysis, ScreeningRecord } from '../../types/screening';
import demoPhotoAsset from './demo-oral-photo.svg';

const panelOptions = ['Photo-assisted oral health review', 'Persistent sore or ulcer', 'Visible mouth change', 'Tobacco or areca exposure'];
const chipStages = ['Photo selected', 'Capture quality reviewed', 'Prior records checked', 'Demo priority generated', 'Report prepared'];
const demoChipStages = ['Demo photo selected', 'Sample image confirmed', 'Prior records checked', 'Demo priority generated', 'Report prepared'];
const scoreFor: Record<DemoScenario, number> = { 'Lower review demo': 24, 'Balanced demo': 49, 'Higher review demo': 78 };

type LocalRecord = ScreeningRecord & { participantCode?: string };
type Props = { onSave: (record: LocalRecord) => void; records: LocalRecord[] };

export function NewScreening({ onSave, records }: Props) {
  const [step, setStep] = useState(0);
  const [scenario, setScenario] = useState<DemoScenario>('Balanced demo');
  const [selectedPanels, setSelectedPanels] = useState<string[]>([panelOptions[0]]);
  const [age, setAge] = useState('');
  const [participantCode, setParticipantCode] = useState('DEMO-01');
  const [language, setLanguage] = useState<'English' | 'Hindi'>('English');
  const [collectedAt, setCollectedAt] = useState(new Date().toISOString().slice(0, 10));
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoUrl, setPhotoUrl] = useState('');
  const [isDemoPhoto, setIsDemoPhoto] = useState(false);
  const [quality, setQuality] = useState({ lighting: false, focus: false, location: false });
  const [consent, setConsent] = useState(false);
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState(-1);
  const [analysis, setAnalysis] = useState<ScreeningAnalysis | null>(null);
  const [error, setError] = useState('');

  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);
  const previous = useMemo(() => records.filter((record) => record.participantCode === participantCode.trim())
    .sort((a, b) => new Date(b.report?.record.collected_at || b.date).getTime() - new Date(a.report?.record.collected_at || a.date).getTime()), [records, participantCode]);
  const panelLabels: Record<string, string> = language === 'Hindi' ? {
    'Photo-assisted oral health review': 'मुख स्वास्थ्य फोटो समीक्षा', 'Persistent sore or ulcer': 'लंबे समय से घाव या छाला',
    'Visible mouth change': 'मुंह में दिखाई देने वाला बदलाव', 'Tobacco or areca exposure': 'तंबाकू या सुपारी का उपयोग',
  } : Object.fromEntries(panelOptions.map((item) => [item, item]));

  function togglePanel(panel: string) {
    setSelectedPanels((current) => current.includes(panel) ? current.filter((item) => item !== panel) : [...current, panel]);
  }
  function selectPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] || null;
    if (!file) return;
    if (!file.type.startsWith('image/')) { setError('Choose an image file.'); return; }
    if (file.size > 12 * 1024 * 1024) { setError('Choose an image smaller than 12 MB.'); return; }
    setError('');
    setPhoto(file);
    setIsDemoPhoto(false);
    setQuality({ lighting: false, focus: false, location: false });
    setPhotoUrl(URL.createObjectURL(file));
  }

  async function createReportFromDemoPhoto() {
    setError('');
    try {
      const response = await fetch(demoPhotoAsset);
      if (!response.ok) throw new Error('Demo photo unavailable');
      const blob = await response.blob();
      const file = new File([blob], 'oralytics-demo-photo.svg', { type: blob.type || 'image/svg+xml' });
      setPhoto(file);
      setIsDemoPhoto(true);
      setPhotoUrl(URL.createObjectURL(file));
      await runAnalysis(file, true);
    } catch {
      setError('The demo photo could not be loaded. Please try again.');
    }
  }

  async function runAnalysis(photoOverride?: File, demoPhotoOverride = false) {
    const selectedPhoto = photoOverride || photo;
    const selectedIsDemoPhoto = demoPhotoOverride || isDemoPhoto;
    setError('');
    if (!consent) { setError('Please confirm consent for this synthetic demo record.'); return; }
    if (!participantCode.trim()) { setError('Enter a pseudonymous participant ID.'); return; }
    if (!selectedPhoto) { setError('Select an oral photo before continuing.'); return; }
    if (!selectedIsDemoPhoto && (!quality.lighting || !quality.focus || !quality.location)) { setError('Review all three photo quality checks before continuing.'); return; }
    if (age && (!Number.isInteger(Number(age)) || Number(age) < 0 || Number(age) > 120)) { setError('Age must be a whole number from 0 to 120.'); return; }
    setRunning(true); setStep(3); setStage(0);
    const timer = window.setInterval(() => setStage((current) => Math.min(current + 1, chipStages.length - 1)), 500);
    try {
      let result: ScreeningAnalysis;
      try {
        result = await api.analyzeScreening({
          sample_type: 'photo', panels: selectedPanels, scenario,
          age: age ? Number(age) : undefined, participant_code: participantCode.trim(), consent, collected_at: collectedAt,
        });
      } catch (reason) {
        if (sessionStorage.getItem('biosentry.demo') !== 'true' || !(reason instanceof ApiError)) throw reason;
        const now = new Date().toISOString();
        const score = scoreFor[scenario];
        result = {
          record: { id: 0, record_code: `DEMO-${Date.now().toString(36).toUpperCase()}`, status: 'Pending review', is_simulated: true, data_source: 'local demo', collected_at: new Date(`${collectedAt}T00:00:00`).toISOString() },
          sample_type: 'photo', scenario, selected_panels: selectedPanels, readings: [], timestamp: now, is_simulated: true,
          participant_code: participantCode.trim(),
          assessment: {
            category: score < 35 ? 'Lower simulated signal' : score < 67 ? 'Intermediate simulated signal' : 'Elevated simulated signal requiring professional review',
            signal_score: score, explanation: [`The “${scenario}” preset selected a synthetic workflow score.`, 'The photo is not analyzed by this demo; no finding or diagnosis is inferred from it.', previous.length ? `Compared with ${previous[0].id}, this is a new time-stamped demo record for the same pseudonymous ID.` : 'This is the first saved demo assessment for this pseudonymous ID.'],
            missing_inputs: age ? [] : ['age'], rule_version: 'local-demo-1', is_simulated: true,
            disclaimer: 'Synthetic workflow demonstration only. The photo is not analyzed and this is not a diagnosis, cancer probability, or medical advice.',
          },
        };
      }
      window.clearInterval(timer);
      setStage(chipStages.length - 1);
      result.participant_code = participantCode.trim();
      const priorScored = previous.find((record) => record.report)?.report;
      const currentScore = result.assessment.signal_score;
      const priorScore = priorScored?.assessment.signal_score;
      const consecutiveElevated = previous.filter((record) => record.report).reduce((count, record) => {
        if (count < 0) return count;
        return record.report!.assessment.signal_score >= 67 ? count + 1 : -1;
      }, 0);
      result.assessment.explanation = [
        ...result.assessment.explanation,
        selectedIsDemoPhoto ? 'Bundled demo illustration used to demonstrate the photo workflow. It is not a real patient image and is not analyzed.' : `Photo capture checklist recorded: ${Object.values(quality).filter(Boolean).length}/3 checks. Image interpretation is not performed by this prototype.`,
        `Patient language preference recorded: ${language}. Context choices map to a shared demo vocabulary.`,
        previous.length ? `Longitudinal context: ${previous.length} earlier assessment(s) exist for this pseudonymous ID; most recent is ${previous[0].id} (${previous[0].date}).` : 'Longitudinal context: no earlier assessment is saved for this pseudonymous ID.',
        priorScore !== undefined ? `Synthetic score comparison: ${priorScore}/100 previously and ${currentScore}/100 now (${currentScore - priorScore >= 0 ? '+' : ''}${currentScore - priorScore}). These scenario-based values are not biological measurements.` : 'A numeric trend is unavailable because no earlier scored report exists for this ID.',
        currentScore >= 67 && consecutiveElevated > 0 ? `The synthetic elevated-priority category has appeared in ${consecutiveElevated} consecutive earlier scored record(s); this is a workflow demonstration, not a persistent abnormality finding.` : '',
      ].filter(Boolean);
      const saved: LocalRecord = {
        id: result.record.record_code, backendId: result.record.id || undefined, date: new Date(result.record.collected_at).toLocaleDateString(),
        sample: 'Oral photo', panels: result.selected_panels, priority: result.assessment.category, status: result.record.status,
        referral: 'Draft', report: result, participantCode: participantCode.trim(),
      };
      onSave(saved); setAnalysis(result); setStep(4);
    } catch (caught) {
      window.clearInterval(timer);
      setError(caught instanceof ApiError ? caught.message : 'The demo could not be completed. Try again.'); setStep(3);
    } finally { setRunning(false); }
  }

  return <main className="page">
    <div className="page-heading"><div><span className="eyebrow">ORAL HEALTH PHOTO WORKFLOW · SIMULATION ONLY</span><h1>New photo review</h1><p>Capture a time-stamped oral photo record and review it alongside prior demo records.</p></div><span className="pill">PHOTO CAPTURE · NO AUTOMATED IMAGE DIAGNOSIS</span></div>
    <div className="wizard"><div className="wizard-main">
      <div className="stepper">{['Record', 'Photo', 'Context', 'Review', 'Report'].map((title, index) => <button key={title} className={step === index ? 'current' : index < step ? 'done' : ''} onClick={() => index < step && setStep(index)}><i>{index < step ? '✓' : index + 1}</i>{title}</button>)}</div>
      {step === 0 && <section className="panel wizard-panel"><PanelTitle title="Assessment record" subtitle="Use a pseudonymous ID so repeat visits can be grouped in this browser."/><div className="fields"><Field label="Participant ID"><input value={participantCode} onChange={(event) => setParticipantCode(event.target.value)} maxLength={80}/></Field><Field label="Age · optional"><input type="number" min="0" max="120" value={age} onChange={(event) => setAge(event.target.value)} placeholder="Age in years"/></Field><Field label="Assessment date"><input type="date" value={collectedAt} onChange={(event) => setCollectedAt(event.target.value)}/></Field><Field label="Patient language preference"><select value={language} onChange={(event) => setLanguage(event.target.value as 'English' | 'Hindi')}><option>English</option><option>Hindi</option></select></Field></div><p className="chart-note">{previous.length ? `${previous.length} earlier record(s) found for this ID. Most recent: ${previous[0].date}.` : 'No earlier records found for this ID.'}</p><label className="check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)}/> Consent recorded for this synthetic demo workflow.</label><div className="actions end"><button className="btn primary" onClick={() => setStep(1)}>Continue <ArrowRight size={16}/></button></div></section>}
      {step === 1 && <section className="panel wizard-panel"><PanelTitle title="Add an oral photo" subtitle="Choose a clear image. It is previewed in this tab only and is not uploaded or retained in the report."/><div className="photo-upload-options"><label className="photo-picker"><ImagePlus size={22}/><span>{photo && !isDemoPhoto ? photo.name : 'Choose or take a photo'}</span><input type="file" accept="image/*" capture="environment" onChange={selectPhoto}/></label><div className="demo-photo-card"><img src={demoPhotoAsset} alt="Illustrative synthetic oral photo sample"/><div className="demo-photo-copy"><span className="pill">BUILT-IN DEMO PHOTO</span><p>Use this illustration to try the report workflow. No real patient image is shown.</p><button className="btn outline" type="button" disabled={running} onClick={createReportFromDemoPhoto}>Create report with demo photo <ArrowRight size={15}/></button></div></div></div>{photoUrl && <img className="photo-preview" src={photoUrl} alt={isDemoPhoto ? 'Illustrative synthetic demo photo preview' : 'Selected oral photo preview'}/>}<h4>Capture quality checklist</h4><p className="chart-note">Confirm these capture conditions yourself. The app does not automatically assess image quality. The bundled demo illustration skips camera quality checks.</p><div className="quality-checks"><label><input type="checkbox" checked={quality.lighting} onChange={(event) => setQuality((value) => ({ ...value, lighting: event.target.checked }))}/> Adequate lighting</label><label><input type="checkbox" checked={quality.focus} onChange={(event) => setQuality((value) => ({ ...value, focus: event.target.checked }))}/> Image appears in focus</label><label><input type="checkbox" checked={quality.location} onChange={(event) => setQuality((value) => ({ ...value, location: event.target.checked }))}/> Area of interest is visible</label></div>{error && <div role="alert" className="error">{error}</div>}<Notice text="This is a photo capture and review workflow only. The prototype does not interpret images or identify lesions."/><div className="actions end"><button className="btn outline" onClick={() => setStep(0)}>Back</button><button className="btn primary" disabled={!photo} onClick={() => setStep(2)}>Continue <ArrowRight size={16}/></button></div></section>}
      {step === 2 && <section className="panel wizard-panel"><PanelTitle title="Symptoms and exposure context" subtitle="Record what should be available to a qualified reviewer. These selections are not a diagnosis."/><div className="panel-options">{panelOptions.map((panel) => <button key={panel} className={selectedPanels.includes(panel) ? 'chosen' : ''} onClick={() => togglePanel(panel)}><span><b>{panelLabels[panel]}</b><small>{panel === panelOptions[0] ? (language === 'Hindi' ? 'फोटो केवल मानव समीक्षा के लिए है' : 'Photo is for human review only') : (language === 'Hindi' ? 'रोगी द्वारा बताया गया संदर्भ' : 'Patient-reported context')}</small></span><i>{selectedPanels.includes(panel) ? '✓' : ''}</i></button>)}</div><Field label="Review priority scenario"><select value={scenario} onChange={(event) => setScenario(event.target.value as DemoScenario)}><option>Balanced demo</option><option>Lower review demo</option><option>Higher review demo</option></select></Field><div className="actions end"><button className="btn outline" onClick={() => setStep(1)}>Back</button><button className="btn primary" onClick={() => setStep(3)}>Continue <ArrowRight size={16}/></button></div></section>}
      {step === 3 && <div className="simulation"><section className="panel wizard-panel"><PanelTitle title="Review and generate demo report" subtitle="The preset creates a synthetic workflow priority; the photo is not processed."/><div className="reading-preview"><small>PROCESSING STAGES</small>{(isDemoPhoto ? demoChipStages : chipStages).map((label, index) => <span key={label} className={stage >= index ? 'stage-done' : ''}><i>{stage > index ? '✓' : index + 1}</i>{label}</span>)}</div>{error && <div role="alert" className="error">{error}</div>}<Notice text="No image-derived measurement or automated diagnosis is produced. Escalation decisions must follow qualified clinical review."/><button className="btn primary full" disabled={running || !consent || !photo} onClick={() => void runAnalysis()}>{running ? 'Preparing demo report…' : 'Generate demo report'} <ArrowRight size={16}/></button></section><section className="chip-card"><div className="chip-header"><div><small>PHOTO WORKFLOW</small><h3>{photo?.name || 'Oral photo'}</h3></div><span className="pill">HUMAN REVIEW</span></div>{photoUrl && <img className="photo-preview" src={photoUrl} alt="Selected oral photo preview"/>}<p className="chip-note">Image remains in this browser tab and is not analyzed or saved to the server.</p></section></div>}
      {step === 4 && analysis && <section className="panel result"><div><span className="pill">● SAVED DEMO REPORT · {analysis.assessment.rule_version}</span><h2>{analysis.assessment.category}</h2><p>Synthetic workflow score: <b>{analysis.assessment.signal_score}/100</b> · not a cancer probability or diagnosis.</p></div><div className="result-grid"><div><small>Screening ID</small><b>{analysis.record.record_code}</b></div><div><small>Assessment</small><b>Oral photo</b></div><div><small>Scenario</small><b>{analysis.scenario}</b></div><div><small>Earlier records</small><b>{previous.length}</b></div></div><h3>Longitudinal context and explanation</h3><ul className="report-explanation">{analysis.assessment.explanation.map((line) => <li key={line}>{line}</li>)}</ul><Notice text={analysis.assessment.disclaimer}/><div className="actions end"><button className="btn outline" onClick={() => window.print()}>Print / save report</button><Link className="btn outline" to={`/records/${encodeURIComponent(analysis.record.record_code)}`}>Open saved report</Link><button className="btn primary" onClick={() => { setStep(0); setAnalysis(null); setPhoto(null); setPhotoUrl(''); setIsDemoPhoto(false); }}>New assessment <Plus size={16}/></button></div></section>}
    </div><aside className="wizard-aside"><section className="aside-card"><ShieldCheck size={20}/><h3>Prototype only</h3><p>No image analysis, cancer detection, or clinical triage is performed. This report demonstrates record keeping and follow-up concepts.</p><ul><li>Photo stays in the current browser tab</li><li>Uploaded photo checks are self-reported; the demo illustration skips them</li><li>Priority is a synthetic scenario</li><li>Real concerns need qualified clinical assessment</li></ul></section><section className="aside-card"><small>RECORD CONTEXT</small><div>Input <b>Oral photo</b></div><div>Scenario <b>{scenario}</b></div><div>Prior records <b>{previous.length}</b></div></section></aside></div>
  </main>;
}

function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) { return <div className="panel-title"><div><h3>{title}</h3><p>{subtitle}</p></div></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
function Notice({ text }: { text: string }) { return <div className="notice"><ShieldCheck size={17}/><span>{text}</span></div>; }
