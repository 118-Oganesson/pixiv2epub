// FILE: src/pixiv2epub/assets/gui/injector.js

(() => {
    const STATUS_SUCCESS = 'success';
    const Z_INDEX = '9999';

    // UIの状態を管理し、必要な時だけDOM操作を行う関数
    const managePixiv2EpubUI = () => {
        // --- 1. 現在のURLから「要求されるUIの状態」を決定する ---
        const url = window.location.href;
        let requiredState = { type: 'none', url: null, buttonText: null };

        if (window.location.host.includes('pixiv.net')) {
            requiredState = {
                type: 'pixiv',
                url: url,
                buttonText: 'このページをEPUB化'
            };
        }

        // --- 2. DOMから「現在のUIの状態」を取得する ---
        const container = document.getElementById('pixiv2epub-gui-container');
        const currentType = container ? container.dataset.pageType : 'none';

        // --- 3. 要求される状態と現在の状態が同じなら、何もしない ---
        if (requiredState.type === currentType) {
            const button = document.getElementById('pixiv2epub-run-button');
            // ボタンが無効（処理中でない）かつ、URLが古い場合のみ更新
            if (button && !button.disabled && container.dataset.currentUrl !== requiredState.url) {
                container.dataset.currentUrl = requiredState.url;
            }
            return;
        }

        // --- 4. 状態が異なる場合、まず既存のUIを削除する ---
        if (container) {
            container.remove();
        }

        // --- 5. 要求される状態が「UI不要」なら、ここで処理を終了 ---
        if (requiredState.type === 'none') {
            return;
        }

        // --- 6. 新しい状態に対応するUIを生成して注入する ---
        const newContainer = document.createElement('div');
        newContainer.id = 'pixiv2epub-gui-container';
        newContainer.dataset.pageType = requiredState.type; // 新しい状態をDOMに保存
        newContainer.dataset.currentUrl = requiredState.url;
        const button = document.createElement('button');
        button.id = 'pixiv2epub-run-button';
        button.textContent = requiredState.buttonText;

        const statusPanel = document.createElement('div');
        statusPanel.id = 'pixiv2epub-status-panel';

        // スタイリング
        Object.assign(newContainer.style, {
            position: 'fixed', bottom: '20px', right: '20px', zIndex: Z_INDEX,
            backgroundColor: 'rgba(240, 248, 255, 0.95)', border: '1px solid #0073ff',
            borderRadius: '8px', padding: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            fontFamily: '"Helvetica Neue", Arial, sans-serif', fontSize: '14px', color: '#333',
            minWidth: '250px', transition: 'all 0.3s ease'
        });
        Object.assign(button.style, {
            width: '100%', padding: '10px', backgroundColor: '#0073ff', color: 'white',
            border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight: 'bold',
            fontSize: '15px', transition: 'background-color 0.2s'
        });
        Object.assign(statusPanel.style, {
            marginTop: '10px', padding: '8px', borderRadius: '4px',
            backgroundColor: '#eee', display: 'none', wordWrap: 'break-word'
        });

        // イベントリスナ
        button.addEventListener('click', async () => {
            button.disabled = true;
            button.textContent = '処理中...';
            statusPanel.style.display = 'block';
            statusPanel.textContent = 'バックエンド処理を開始しました。コンソールのログを確認してください。';
            statusPanel.style.color = '#555';
            statusPanel.style.backgroundColor = '#e0e0e0';

            try {
                const urlToProcess = newContainer.dataset.currentUrl;
                const result = await window.pixiv2epub_run(urlToProcess);

                if (result.status === STATUS_SUCCESS) {
                    statusPanel.textContent = `成功: ${result.message}`;
                    statusPanel.style.color = '#1a7431';
                    statusPanel.style.backgroundColor = '#d4edda';
                } else {
                    // バックエンドからのエラーメッセージ (例: "無効なURLです") をそのまま表示
                    statusPanel.textContent = `失敗: ${result.message}`;
                    statusPanel.style.color = '#721c24';
                    statusPanel.style.backgroundColor = '#f8d7da';
                }
            } catch (error) {
                statusPanel.textContent = `通信エラー: ${error.message || error}`;
                statusPanel.style.color = '#721c24';
                statusPanel.style.backgroundColor = '#f8d7da';
            } finally {
                button.disabled = false;
                button.textContent = requiredState.buttonText;
            }
        });

        // DOMへの追加
        newContainer.appendChild(button);
        newContainer.appendChild(statusPanel);
        document.body.appendChild(newContainer);
    };

    // --- メイン実行ロジック ---
    document.addEventListener('DOMContentLoaded', () => {
        // 初回ロード時に実行
        managePixiv2EpubUI();

        // SPAでのページ遷移を監視するためにMutationObserverを設定
        const observer = new MutationObserver(() => {
            // DOMの変更後、URLが更新されるのを少し待ってからUIを管理する
            setTimeout(managePixiv2EpubUI, 100);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
})();