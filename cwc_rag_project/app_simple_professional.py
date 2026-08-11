from flask import Flask, jsonify, render_template_string, request
import argparse
from rag_query import CWCRag

app = Flask(__name__)
rag = None

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CWC Reservoir RAG Assistant</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f5f8fc;color:#1f2937}
.container{width:92%;max-width:900px;margin:auto}
.header{background:#fff;border-bottom:1px solid #e5e7eb}
.header-content{min-height:70px;display:flex;align-items:center;justify-content:space-between}
.brand{display:flex;align-items:center;gap:12px}
.logo{width:42px;height:42px;border-radius:10px;background:#0b63a8;color:#fff;display:grid;place-items:center;font-size:21px}
.brand h1{margin:0;font-size:19px;color:#12344d}
.brand p{margin:3px 0 0;font-size:12px;color:#6b7280}
.status{font-size:12px;font-weight:bold;color:#16845b}
.main{padding:42px 0 55px}
.intro{text-align:center;margin-bottom:28px}
.intro h2{margin:0 0 12px;font-size:32px;color:#12344d}
.intro p{max-width:680px;margin:auto;color:#667085;font-size:15px;line-height:1.7}
.search-card,.answer-section{background:#fff;border:1px solid #e1e7ef;border-radius:14px;box-shadow:0 5px 20px rgba(15,40,65,.07)}
.search-card{padding:20px}
.search-label{display:block;margin-bottom:9px;font-size:13px;font-weight:bold;color:#344054}
.search-row{display:flex;gap:10px}
#question{flex:1;height:48px;padding:0 14px;border:1px solid #d0d5dd;border-radius:9px;outline:none;font-size:14px}
#question:focus{border-color:#0b63a8;box-shadow:0 0 0 3px rgba(11,99,168,.1)}
#ask-button{height:48px;padding:0 22px;border:0;border-radius:9px;background:#0b63a8;color:#fff;font-weight:bold;cursor:pointer}
#ask-button:hover{background:#084f87}
#ask-button:disabled{background:#8baec9;cursor:not-allowed}
.examples{margin-top:22px}
.examples-title{font-size:13px;font-weight:bold;color:#344054;margin-bottom:10px}
.question-buttons{display:flex;flex-wrap:wrap;gap:8px}
.example-button{background:#fff;border:1px solid #d9e1ea;color:#34536d;border-radius:20px;padding:8px 12px;font-size:12px;cursor:pointer}
.example-button:hover{border-color:#0b63a8;color:#0b63a8}
.answer-section{display:none;margin-top:25px;overflow:hidden}
.answer-header{padding:15px 18px;border-bottom:1px solid #e5e7eb;display:flex;align-items:center;justify-content:space-between}
.answer-header h3{margin:0;font-size:15px;color:#12344d}
.clear-button{border:1px solid #d9e1ea;background:#fff;color:#667085;padding:6px 10px;border-radius:7px;cursor:pointer;font-size:12px}
.answer-body{padding:20px}
.answer-label{color:#0b63a8;font-size:11px;font-weight:bold;text-transform:uppercase;margin-bottom:8px}
#answer{white-space:pre-wrap;line-height:1.7;font-size:14px;color:#344054}
.source{margin-top:18px;padding-top:14px;border-top:1px solid #eef1f4;color:#667085;font-size:12px}
.loading{display:none;padding:20px;color:#667085;font-size:13px}
.spinner{display:inline-block;width:15px;height:15px;margin-right:8px;vertical-align:-3px;border:2px solid #d9e6f0;border-top-color:#0b63a8;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.footer{text-align:center;color:#98a2b3;font-size:11px;margin-top:35px}
@media(max-width:650px){.status{display:none}.intro h2{font-size:26px}.search-row{flex-direction:column}#ask-button{width:100%}}
</style>
</head>
<body>
<header class="header"><div class="container header-content">
<div class="brand"><div class="logo">💧</div><div><h1>CWC Reservoir RAG Assistant</h1><p>Weekly Reservoir Bulletin Analysis</p></div></div>
<div class="status">● System Ready</div>
</div></header>

<main class="main container">
<section class="intro">
<h2>Ask About Reservoir Data</h2>
<p>Get answers from the latest CWC weekly reservoir bulletin. Ask about individual reservoirs, storage levels, regions, basins, rainfall or storage comparisons.</p>
</section>

<section class="search-card">
<label class="search-label" for="question">Enter your question</label>
<form id="question-form" class="search-row">
<input id="question" type="text" maxlength="500" autocomplete="off" placeholder="Example: What is the current storage of Tehri?">
<button id="ask-button" type="submit">Ask</button>
</form>

<div class="examples">
<div class="examples-title">Example questions</div>
<div class="question-buttons">
<button class="example-button" data-question="What is the current live storage of Tehri dam?">Current storage of Tehri</button>
<button class="example-button" data-question="How much has Nagarjuna Sagar's storage changed compared to normal?">Nagarjuna Sagar comparison</button>
<button class="example-button" data-question="Which region has storage better than last year?">Regional storage comparison</button>
<button class="example-button" data-question="Which basins are in deficient or highly deficient category?">Basin status</button>
<button class="example-button" data-question="List reservoirs in Tamil Nadu with less than 50% of normal storage.">Tamil Nadu reservoirs</button>
</div></div>
</section>

<section id="answer-section" class="answer-section">
<div class="answer-header"><h3>Answer</h3><button id="clear-button" class="clear-button">Clear</button></div>
<div id="loading" class="loading"><span class="spinner"></span>Searching the CWC data and generating the answer...</div>
<div id="answer-body" class="answer-body">
<div class="answer-label">CWC RAG Assistant</div>
<div id="answer"></div>
<div id="source" class="source"></div>
</div>
</section>
<div class="footer">CWC Reservoir RAG Assistant · Retrieval-Augmented Generation</div>
</main>

<script>
const form=document.getElementById("question-form");
const question=document.getElementById("question");
const askButton=document.getElementById("ask-button");
const answerSection=document.getElementById("answer-section");
const answerBody=document.getElementById("answer-body");
const answer=document.getElementById("answer");
const source=document.getElementById("source");
const loading=document.getElementById("loading");

async function askQuestion(text){
    const q=text.trim();
    if(!q){question.focus();return;}
    answerSection.style.display="block";
    answerBody.style.display="none";
    loading.style.display="block";
    askButton.disabled=true;
    askButton.textContent="Processing...";
    try{
        const response=await fetch("/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q:q})});
        const data=await response.json();
        if(!response.ok||data.error) throw new Error(data.error||"Unable to process the question.");
        answer.textContent=data.answer||"No answer was returned.";
        if(data.structured_row&&data.structured_row.bulletin_date){
            source.textContent="Data source: CWC weekly bulletin dated "+data.structured_row.bulletin_date;
        }else{
            source.textContent="Data source: Relevant sections from the CWC weekly bulletin.";
        }
        answerBody.style.display="block";
    }catch(error){
        answer.textContent="Unable to process your question. Please check the RAG system and try again.";
        source.textContent=error.message;
        answerBody.style.display="block";
    }finally{
        loading.style.display="none";
        askButton.disabled=false;
        askButton.textContent="Ask";
    }
}
form.addEventListener("submit",e=>{e.preventDefault();askQuestion(question.value);});
document.querySelectorAll(".example-button").forEach(button=>{
    button.addEventListener("click",()=>{question.value=button.dataset.question;askQuestion(question.value);});
});
document.getElementById("clear-button").addEventListener("click",()=>{
    question.value="";answer.textContent="";source.textContent="";answerSection.style.display="none";question.focus();
});
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(PAGE)

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data=request.get_json(silent=True) or {}
        question=str(data.get("q","")).strip()
        if not question:
            return jsonify({"error":"Please enter a question."}),400
        if len(question)>500:
            return jsonify({"error":"Please keep your question under 500 characters."}),400
        if rag is None:
            return jsonify({"error":"The RAG system is not initialized."}),503
        return jsonify(rag.ask(question))
    except Exception:
        app.logger.exception("RAG request failed")
        return jsonify({"error":"Unable to process the question. Please check the RAG data and API configuration."}),500

if __name__=="__main__":
    parser=argparse.ArgumentParser(description="CWC Reservoir RAG Assistant")
    parser.add_argument("--datadir",default="./data")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=5000)
    args=parser.parse_args()
    print("[app] Loading CWC RAG system...")
    rag=CWCRag(args.datadir)
    print("[app] CWC Reservoir RAG Assistant is ready.")
    print(f"[app] Open http://{args.host}:{args.port}")
    app.run(host=args.host,port=args.port,debug=False)
