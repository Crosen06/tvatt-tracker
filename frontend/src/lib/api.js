export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body, isForm = false) {
  const init = { method };
  if (body !== undefined) {
    init.body = isForm ? body : JSON.stringify(body);
    if (!isForm) init.headers = { "Content-Type": "application/json" };
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Ingen kontakt med tvätt-trackern. Kontrollera att du är på hemmets wifi.");
  }
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) throw new ApiError(res.status, data?.detail || `Något gick fel (fel ${res.status}).`);
  return data;
}

export const api = {
  get: (p) => request("GET", p),
  post: (p, b) => request("POST", p, b),
  patch: (p, b) => request("PATCH", p, b),
  del: (p) => request("DELETE", p),
  upload: (p, formData) => request("POST", p, formData, true),
};
