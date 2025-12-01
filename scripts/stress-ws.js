// Node.js script to create many WS connections and send messages
// Usage: node stress-ws.js <url> <connections> <messagesPerConn>
const WebSocket = require('ws');
const url = process.argv[2] || 'wss://your-app.onrender.com/ws';
const N = parseInt(process.argv[3]||50);
const M = parseInt(process.argv[4]||2);

console.log(`Connecting ${N} sockets to ${url}`);
let sockets = [];
for(let i=0;i<N;i++){
  const ws = new WebSocket(url);
  ws.on('open', ()=>{
    for(let k=0;k<M;k++){
      ws.send(JSON.stringify({ author: 'bot'+i, text: 'hello '+k }));
    }
    // optionally close after short delay
    setTimeout(()=>ws.close(), 2000);
  });
  ws.on('message', (m)=>{ /*console.log('msg',m.toString())*/ });
  sockets.push(ws);
}
