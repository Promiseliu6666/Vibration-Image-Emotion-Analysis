"""Compatibility redirect; authentication lives only in the original system."""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
app=FastAPI(docs_url=None,redoc_url=None)
@app.get('/{path:path}')
async def redirect(path:str):
 return RedirectResponse('http://127.0.0.1:5173/',status_code=307,headers={'Cache-Control':'no-store'})
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8800)
