import { useEffect, useState } from 'react';
import axios from 'axios';

interface ApiResponse {
  message: string;
}

const App: React.FC = () => {
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    axios.get<ApiResponse>('http://localhost:5000/api/hello')
      .then(res => setMessage(res.data.message))
      .catch(err => console.error(err));
  }, []);

  return <h1>{message}</h1>;
};

export default App;