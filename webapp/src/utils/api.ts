export async function search(first: string, last: string, company: string) {
    const url = "http://localhost:5000/generate_bio";
    const payload = { first, last, company };
  
    const response = await fetch(url, {
      method: "POST",
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
  
    return response.json();
  }