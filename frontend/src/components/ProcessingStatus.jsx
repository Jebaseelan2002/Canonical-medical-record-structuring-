export default function ProcessingStatus({result}) {
  if (!result) return null;

  const valid = result.validation?.results?.filter(item => item.valid).length || 0;
  const storageMessage = result.stored
    ? `Stored in ${result.storage_backend === 'mongodb' ? 'MongoDB' : result.storage_backend}.`
    : 'Record storage was not confirmed.';

  return <div className="card">
    <h2>Processing complete</h2>
    <p>{result.pages} page(s) processed. {result.resources.length} FHIR resource(s). {valid}/{result.resources.length} passed HAPI validation.</p>
    <p>{storageMessage} RAG vector: {result.vector_backend || 'not created'}.</p>
  </div>;
}
