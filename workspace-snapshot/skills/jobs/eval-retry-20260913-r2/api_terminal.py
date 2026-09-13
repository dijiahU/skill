import argparse,fcntl,json,os,time
from contextlib import ExitStack
from openai import OpenAI
from api_benchmarks.bridge_process import chat_bridge
from terminal_common import JOB,PLAN,run_terminal
from lifecycle import save

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',choices=['gpt','gemini'],required=True);model=p.parse_args().model
    lock=(JOB/f'terminal-{model}.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    base=PLAN['terminal_plan'];definition=base['models'][model]
    with ExitStack() as stack:
        key=os.environ[definition['key_env']];url=base['base_url']
        if definition['bridge']:
            bridge=stack.enter_context(chat_bridge(dict(os.environ,BRIDGE_MAX_OUTPUT_TOKENS='8192',BRIDGE_ADVERTISE_HOST='127.0.0.1'),{'id':definition['id'],'base_url':url,'key':key},'/srv/benchmark/skills/envs/api-harbor-20260912/bin/python',JOB/'frozen',JOB/'logs'/model))
            key,url=bridge['OPENAI_API_KEY'],bridge['BRIDGE_LOCAL_BASE_URL']
        client=OpenAI(api_key=key,base_url=url,timeout=120,max_retries=0)
        completed=False
        with client.responses.create(model=definition['id'],input=[{'role':'user','content':'Reply OK.'}],max_output_tokens=512,stream=True) as stream:
            for event in stream:
                if event.type in ['error','response.failed']:raise RuntimeError('API preflight failed')
                if event.type=='response.completed':completed=True;break
        if not completed:raise RuntimeError('No completed response')
        save(JOB/'preflight'/f'terminal-{model}.json',{'passed':True,'time':time.time()})
        run_terminal(model,url,key)
if __name__=='__main__':main()
