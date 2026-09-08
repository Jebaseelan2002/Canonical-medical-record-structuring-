import {useEffect,useState} from 'react';
import UploadForm from './components/UploadForm';
import ProcessingStatus from './components/ProcessingStatus';
import {getRecords} from './services/api';

export default function App(){
  const [result,setResult]=useState(null);
  const [activeRecordId,setActiveRecordId]=useState('');
  const [history,setHistory]=useState([]);
  const [query,setQuery]=useState('');
  const [searching,setSearching]=useState(false);
  const [rag,setRag]=useState(null);
  const [messages,setMessages]=useState([]);
  const [error,setError]=useState('');

  async function refreshHistory(nextQuery='') {
    setSearching(true);
    try {
      const data = await getRecords(nextQuery);
      setHistory(data.results || []);
      setRag(nextQuery.trim() ? data : null);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  useEffect(()=>{refreshHistory();},[]);

  async function handleUploadComplete(uploadResult){
    setResult(uploadResult);
    setActiveRecordId(uploadResult.record_id || '');
    setMessages([]);
    setRag(null);
    await refreshHistory();
  }

  async function handleSearch(e){
    e.preventDefault();
    const question=query.trim();
    if(!question||searching)return;
    setMessages(current=>[...current,{role:'user',content:question}]);
    setQuery('');
    setSearching(true);
    try {
      const data=await getRecords(question,activeRecordId);
      setHistory(data.results||[]);
      setRag(data);
      setMessages(current=>[...current,{role:'assistant',content:data.answer||'I could not find an answer.'}]);
      setError('');
    } catch(err) {
      setMessages(current=>[...current,{role:'assistant',content:`I could not complete that request: ${err.message}`}]);
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  return <main>
    <header><h1>Canonical Medical FHIR</h1></header>
    <UploadForm onDone={handleUploadComplete}/>
    {error&&<p className="error">{error}</p>}
    <ProcessingStatus result={result}/>
    <section className="card">
      <h2>Medical Records Assistant</h2>
      <p className="chat-caption">Ask a question about the stored medical records.</p>
      <div className="chat-window" aria-live="polite">
        {!messages.length&&<p className="chat-empty">Ask about diagnoses, medications, observations, or patient details.</p>}
        {messages.map((message,index)=><div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
          <strong>{message.role==='user'?'You':'Assistant'}</strong>
          <p>{message.content}</p>
        </div>)}
        {searching&&messages.length>0&&<div className="chat-message assistant"><strong>Assistant</strong><p>Reviewing the stored records...</p></div>}
      </div>
      <form className="query-form" onSubmit={handleSearch}>
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ask about the medical records..." aria-label="Ask the medical records assistant" />
        <button type="submit" disabled={searching||!query.trim()}>{searching?'Thinking...':'Send'}</button>
      </form>
    </section>
  </main>
}
