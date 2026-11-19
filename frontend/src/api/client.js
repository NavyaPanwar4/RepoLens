import axios from "axios"

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
})

const apiKey = import.meta.env.VITE_API_KEY
if (apiKey) {
  client.defaults.headers.common["X-API-Key"] = apiKey
}

export default client
