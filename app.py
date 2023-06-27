import streamlit as st
import requests
import json
import datetime
import pytz
import xml.etree.ElementTree as ET
import openai


# arXiv APIのエンドポイント
arxiv_api_url = 'http://export.arxiv.org/api/query'


def parse_xml(xml_data):
    # XMLデータを解析してタイトル、要約、投稿日時を抽出する
    root = ET.fromstring(xml_data)
    papers = []
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        title = entry.find('{http://www.w3.org/2005/Atom}title').text
        summary = entry.find('{http://www.w3.org/2005/Atom}summary').text
        published = entry.find('{http://www.w3.org/2005/Atom}published').text
        papers.append({'title':title, 'summary':summary, 'published':published})
    return papers


def search_arxiv_papers(query, start_date=None, end_date=None):
    # arXiv APIのエンドポイントとパラメータを指定
    base_url = 'http://export.arxiv.org/api/query'

    # クエリパラメータの設定
    params = {
        'search_query': f'{query} AND submittedDate:[{start_date} TO {end_date}235959]',
        'max_results': 5,  # 取得する論文の最大数
        'sortBy': 'relevance',  # 関連性に基づいてソート
        'sortOrder': 'descending',  # 降順にソート
    }

    # APIリクエストを送信してレスポンスを取得
    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        # レスポンスのXMLデータを解析してタイトルと要約を取得
        xml_data = response.content
        papers = parse_xml(xml_data)
        return papers
    else:
        print('Failed to fetch papers from arXiv API.')
        return []


def generate_summary(text):
    # ChatGPT APIを使用して要約を生成
    functions = [
    {
        "name": "output_format",
        "description": "あなたは研究者です。以下の論文の要約文章を読んで、以下の4つの問いに日本語で答えてください。",
        "parameters": {
        "type": "object",
        "properties": {
            "short_summary": {
            "type": "string",
            "description": "この研究を一言で表すと",
            },
            "problem": {
            "type": "string",
            "description": "既存研究の問題点や課題は？",
            },
            "how": {
            "type": "string",
            "description": "この研究ではどのようなアプローチを行ったのか？",
            },
            "result": {
            "type": "string",
            "description": "どのような結果や結論が得られたか",
            },
        },
        "required": ["short_summary","problem", "how", "result"],
        },
    }
    ]
    # content = '''あなたは研究者です。以下の論文の要約文章を読んで、以下の問いに日本語で答えてください。
    # - この研究を一言で表現すると？
    # - 既存研究の問題点や課題は？
    # - この研究ではどのようなアプローチを行ったのか？
    # - どのような結果や結論が得られたか
    # '''
    if st.session_state["api_key"] == "":
        import pickle

        # 保存したresponseオブジェクトを読み込むファイルパス
        file_path = "../response.pkl"

        # pickleファイルからresponseオブジェクトを読み込む
        with open(file_path, "rb") as file:
            response = pickle.load(file)
    else:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            functions=functions,
            messages=[
                # {"role":"system", "content":content},#精度はこれがある方がよい
                {"role": "user", "content": text},
            ],
        )
        if response.status_code != 200:
            st.error('Failed to generate summary using ChatGPT API.')

    
    output_msg = response["choices"][0]["message"]["function_call"]["arguments"]
    output_dict = json.loads(output_msg)
    return output_dict
    
        
def set_api():
    openai.api_key = st.session_state["api_key"]




def main():
    st.title('論文要約アプリ')

    #API入力
    api_key = st.text_input("OpenAI APIキーを入力してください", on_change=set_api, key='api_key')

    # キーワードの入力
    query = st.text_input('キーワードを入力してください')
    # 検索期間の指定
    start_date_input = st.text_input('開始日をYYYYMMDD形式で入力してください（未入力の場合は直近1週間になります）')
    end_date_input = st.text_input('終了日をYYYYMMDD形式で入力してください（未入力の場合は現在日時になります）')
    if "papers" not in st.session_state:
        st.session_state['papers'] = None
    
    

    # 検索ボタンが押された場合の処理
    if st.button('検索', key='search_button'):
        if query:
            
            # JST（日本時間）のタイムゾーンを設定
            jst = pytz.timezone('Asia/Tokyo')

            # 現在の日付を取得（JST）
            now = datetime.datetime.now(jst)

            # 1週間前の日付を計算
            one_week_ago = now - datetime.timedelta(weeks=1)

            # YYYYMMDD形式の文字列をdatetimeオブジェクトに変換
            start_date = start_date_input if start_date_input else one_week_ago.strftime('%Y%m%d')
            end_date = end_date_input if end_date_input else now.strftime('%Y%m%d')
            st.write(start_date)
            # arXiv APIを使用して論文を検索
            papers = search_arxiv_papers(query, start_date, end_date)
            if papers:
                st.session_state['papers']= papers
            else:
                st.warning('該当する論文が見つかりませんでした。')
    
    # 論文の検索結果を表示
    if st.session_state['papers']:
        papers = st.session_state['papers']
        st.subheader('検索結果')
        for i, paper in enumerate(papers, start=1):
            title = paper['title']
            summary = paper['summary']
            published = paper['published']
            st.markdown(f'**論文 {i}**')
            st.write('**タイトル:**', title)
            st.write('**投稿日時:**', published)
            st.write('**要約:**', summary)
            st.write('---')
            
            
            if st.button(f'論文 {i} に質問する', key=f'question_button_{i}'):
                # 論文の要約を生成
                st.session_state['papers'][i-1]['paper_summary']  = generate_summary(summary)
                paper_summary = paper['paper_summary']
                st.write('**この研究を一言で表すと:**', paper_summary['short_summary'])
                st.write('**既存研究の問題点や課題は?:**', paper_summary['problem'])
                st.write('**この研究ではどのようなアプローチを行ったのか?:**', paper_summary['how'])
                st.write('**どのような結果や結論が得られたか?:**', paper_summary['result'])
        

            else:
                if 'paper_summary' in paper.keys():
                    # 生成された要約を表示
                    paper_summary = paper['paper_summary']
                    st.write('**この研究を一言で表すと:**\n', paper_summary['short_summary'])
                    st.write('**既存研究の問題点や課題は?:**', paper_summary['problem'])
                    st.write('**この研究ではどのようなアプローチを行ったのか?:**', paper_summary['how'])
                    st.write('**どのような結果や結論が得られたか?:**', paper_summary['result'])
        

                



if __name__ == '__main__':
    main()
