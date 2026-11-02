import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, MapPin, Search, ShieldCheck } from 'lucide-react';
import { CircleMarker, MapContainer, TileLayer, useMap } from 'react-leaflet';
import { api, ApiError, type Facility, type Referral } from '../../services/api';

const statuses = ['Draft', 'Pending review', 'Referred', 'Appointment recorded', 'Follow-up completed', 'Cancelled'];

export function Referrals() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [referrals, setReferrals] = useState<Referral[]>(() => {
    try { return JSON.parse(localStorage.getItem('biosentry.demo-referrals') || '[]') as Referral[]; } catch { return []; }
  });
  const [selected, setSelected] = useState<Facility | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('All statuses');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [screeningId] = useState(() => Number(sessionStorage.getItem('biosentry.referral.screening') || 0));

  useEffect(() => {
    let active = true;
    api.getFacilities().then((items) => { if (active) { setFacilities(items); setSelected(items[0] || null); } }).catch((reason: unknown) => {
      if (!active) return;
      if (sessionStorage.getItem('biosentry.demo') === 'true') {
        const demoFacilities: Facility[] = [
          { id: 1, name: 'Community Demo Centre', type: 'Primary healthcare centre', address: 'Synthetic location · New Delhi', latitude: 28.6139, longitude: 77.209, data_source: 'synthetic demo', is_simulated: true },
          { id: 2, name: 'North District Demo Hospital', type: 'District hospital', address: 'Synthetic location · Mumbai', latitude: 19.076, longitude: 72.8777, data_source: 'synthetic demo', is_simulated: true },
          { id: 3, name: 'Riverbend Primary Care', type: 'Primary healthcare centre', address: 'Synthetic location · Bengaluru', latitude: 12.9716, longitude: 77.5946, data_source: 'synthetic demo', is_simulated: true },
        ];
        setFacilities(demoFacilities); setSelected(demoFacilities[0]);
      } else setError(reason instanceof ApiError ? reason.message : 'Facility directory could not be loaded.');
    });
    if (sessionStorage.getItem('biosentry.demo') !== 'true') {
      api.listReferrals().then((items) => { if (active) setReferrals(items); }).catch(() => undefined);
    }
    return () => { active = false; };
  }, []);

  const visibleFacilities = useMemo(() => facilities.filter((facility) => `${facility.name} ${facility.type} ${facility.address}`.toLowerCase().includes(query.toLowerCase())), [facilities, query]);
  const visibleReferrals = referrals.filter((referral) => status === 'All statuses' || referral.status === status);

  async function startReferral(facility: Facility) {
    setError(''); setMessage('');
    if (!screeningId && sessionStorage.getItem('biosentry.demo') !== 'true') { setError('Open this page from a saved screening report to start its referral workflow.'); return; }
    if (sessionStorage.getItem('biosentry.demo') === 'true') {
      const referral: Referral = { id: Date.now(), screening_id: screeningId, screening_code: sessionStorage.getItem('biosentry.referral.code') || undefined, facility_id: facility.id, reason: 'Demo screening follow-up navigation', priority: 'Pending review', status: 'Draft', status_history: [{ status: 'Draft', at: new Date().toISOString() }], is_simulated: true };
      setReferrals((current) => { const next = [referral, ...current]; localStorage.setItem('biosentry.demo-referrals', JSON.stringify(next)); return next; });
      setMessage(`Demo referral saved as Draft for ${facility.name}.`);
      return;
    }
    try {
      const referral = await api.createReferral({ screening_id: screeningId, facility_id: facility.id, reason: 'Demo screening follow-up navigation', priority: 'Pending review', status: 'Draft' });
      setReferrals((current) => [referral, ...current]);
      setMessage(`Referral ${referral.id} saved as Draft for ${facility.name}.`);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Referral could not be saved.'); }
  }

  async function changeStatus(referral: Referral, next: string) {
    if (sessionStorage.getItem('biosentry.demo') === 'true') {
      const history = [...referral.status_history, { status: next, at: new Date().toISOString() }];
      setReferrals((items) => { const updated = items.map((item) => item.id === referral.id ? { ...item, status: next, status_history: history } : item); localStorage.setItem('biosentry.demo-referrals', JSON.stringify(updated)); return updated; });
      setMessage(`Demo referral ${referral.id} updated to ${next}.`);
      return;
    }
    try {
      const updated = await api.updateReferralStatus(referral.id, next);
      setReferrals((items) => items.map((item) => item.id === referral.id ? { ...item, status: updated.status, status_history: updated.status_history } : item));
      setMessage(`Referral ${referral.id} updated to ${next}.`);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Referral status could not be updated.'); }
  }

  return <main className="page"><div className="page-heading"><div><span className="eyebrow">CARE NAVIGATION · SYNTHETIC DIRECTORY</span><h1>Referral navigation</h1><p>Choose a demo facility and save a referral workflow for a screening record.</p></div><span className="pill">DEMO FACILITIES ONLY</span></div>
    <div className="notice"><ShieldCheck size={17}/><span>Facility entries and locations are synthetic. No phone numbers, appointments, capacity, or specialist access are represented.</span></div>
    {message && <div className="notice" role="status">{message}</div>}{error && <div className="error" role="alert">{error}</div>}
    <div className="referral-layout"><section className="panel"><div className="panel-title"><div><h3>Demo facilities</h3><p>{facilities.length} synthetic directory entries · search by name or facility type</p></div></div>
      <label className="facility-search"><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search demo facilities"/></label>
      {visibleFacilities.length === 0 && <div className="empty">No demo facilities match this search.</div>}
      {visibleFacilities.map((facility) => <article className={`facility ${selected?.id === facility.id ? 'selected-facility' : ''}`} key={facility.id} onClick={() => setSelected(facility)}><MapPin/><span><b>{facility.name}</b><small>{facility.type} · {facility.address} · synthetic data</small></span><button className="btn outline" onClick={(event) => { event.stopPropagation(); void startReferral(facility); }}>Start referral</button></article>)}
    </section><section className="panel"><div className="panel-title"><div><h3>Facility map</h3><p>OpenStreetMap background · synthetic markers</p></div></div>{facilities.length ? <div className="real-map"><MapContainer center={[22.8,79.2]} zoom={4} scrollWheelZoom style={{height:'100%',width:'100%'}}><TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>{facilities.filter((facility) => facility.latitude !== null && facility.longitude !== null).map((facility) => <CircleMarker key={facility.id} center={[facility.latitude!,facility.longitude!]} radius={selected?.id === facility.id ? 12 : 8} pathOptions={{color:selected?.id === facility.id ? '#087b73' : '#36a88f',fillColor:'#4bc3a7',fillOpacity:.62}} eventHandlers={{click:()=>setSelected(facility)}}/>)}</MapContainer></div> : <div className="empty">No facilities are available.</div>}{selected&&<div className="facility-detail"><b>{selected.name}</b><small>{selected.type} · {selected.address}</small><small>{selected.data_source} · availability and contact details are not provided.</small></div>}<p className="chart-note">Distances are not displayed because this synthetic directory does not include routing data.</p></section></div>
    <section className="panel referral-history"><div className="panel-title"><div><h3>Saved referral workflows</h3><p>Referral status changes are stored with timestamps in the backend.</p></div><select value={status} onChange={(event)=>setStatus(event.target.value)}><option>All statuses</option>{statuses.map((item)=><option key={item}>{item}</option>)}</select></div>{visibleReferrals.length === 0 ? <div className="empty">No saved referrals yet.</div> : visibleReferrals.map((referral)=><div className="saved-referral" key={referral.id}><span><b>Referral #{referral.id}</b><small>Screening record {referral.screening_code || `#${referral.screening_id}`} · {referral.reason}</small></span><select value={referral.status} onChange={(event)=>void changeStatus(referral,event.target.value)}>{statuses.map((item)=><option key={item}>{item}</option>)}</select></div>)}</section>
  </main>;
}
