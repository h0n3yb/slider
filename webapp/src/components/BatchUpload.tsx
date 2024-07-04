import { useState } from 'react';
import LoadingSpinner from './LoadingSpinner';

export default function BatchUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setFile(event.target.files[0]);
    }
  };

  const handleBatchGeneration = async () => {
    if (!file) {
      alert("Please select a CSV file first.");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:5000/generate_batch_bio', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      downloadCSV(data.results);
    } catch (error) {
      console.error('Error:', error);
      alert("Batch processing failed. Please try again.");
    }

    setLoading(false);
    setFile(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex space-x-4">
        <label htmlFor="csvFile" className="flex-1 py-3 px-4 bg-white text-[#8f99fb] font-semibold rounded-lg cursor-pointer hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#8f99fb] focus:ring-opacity-50 text-center">
          Upload CSV
        </label>
        <input 
          type="file" 
          id="csvFile" 
          accept=".csv" 
          className="hidden"
          onChange={handleFileChange}
        />
        <button 
          onClick={handleBatchGeneration}
          className="w-full py-3 bg-[#7A85E1] text-white font-semibold rounded-lg hover:bg-opacity-90 focus:outline-none focus:ring-2 focus:ring-[#7A85E1] focus:ring-opacity-50 shadow-md"
        >
          Generate
        </button>
      </div>
      {file && <div className="text-white text-center">Uploaded: {file.name}</div>}
      {loading && <LoadingSpinner />}
    </div>
  );
}

function downloadCSV(results: Array<{ name: string; company: string; email: string; bio: string }>) {
  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "Name,Company,Email,Bio\n";
  
  results.forEach(result => {
    const row = [
      result.name,
      result.company,
      result.email,
      result.bio
    ].map(e => e ? `"${e.replace(/"/g, '""')}"` : "").join(",");
    csvContent += row + "\n";
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "generated_bios.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}