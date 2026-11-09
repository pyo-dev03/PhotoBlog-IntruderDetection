package com.example.photoviewer;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.materialswitch.MaterialSwitch;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 편의기능 ④ : 로그인(토큰 발급) · 서버 주소 전환 화면
 *  - ID/PW → POST /api-token-auth/ → 토큰을 Keystore 로 암호화 저장
 *  - 로컬(10.0.2.2:8000) ↔ 클라우드(PythonAnywhere) 서버를 앱 재빌드 없이 전환
 */
public class SettingsActivity extends AppCompatActivity {
    private AppSettings settings;
    private TextInputEditText editServer;
    private TextInputEditText editUsername;
    private TextInputEditText editPassword;
    private TextView textLoginState;
    private TextView textTokenInfo;
    private Button btnLogin;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_settings);
        SystemBars.applyPadding(findViewById(R.id.root));

        MaterialToolbar toolbar = findViewById(R.id.toolbar);
        toolbar.setNavigationIcon(R.drawable.ic_arrow_back);
        toolbar.setNavigationOnClickListener(v -> finish());

        settings = new AppSettings(this);
        editServer = findViewById(R.id.editServer);
        editUsername = findViewById(R.id.editUsername);
        editPassword = findViewById(R.id.editPassword);
        textLoginState = findViewById(R.id.textLoginState);
        textTokenInfo = findViewById(R.id.textTokenInfo);
        btnLogin = findViewById(R.id.btnLogin);

        editServer.setText(settings.getServerUrl());
        findViewById(R.id.btnPresetLocal).setOnClickListener(v -> editServer.setText(AppSettings.LOCAL_URL));
        findViewById(R.id.btnPresetCloud).setOnClickListener(v -> editServer.setText(AppSettings.CLOUD_URL));
        findViewById(R.id.btnSaveServer).setOnClickListener(v -> {
            settings.setServerUrl(serverInput());
            editServer.setText(settings.getServerUrl());
            Toast.makeText(this, "서버 주소 저장: " + settings.getServerUrl(), Toast.LENGTH_SHORT).show();
            render();
        });
        btnLogin.setOnClickListener(v -> login());
        findViewById(R.id.btnLogout).setOnClickListener(v -> {
            settings.logout();
            render();
        });

        MaterialSwitch simulate = findViewById(R.id.switchSimulate);
        simulate.setChecked(settings.isSimulateFailure());
        simulate.setOnCheckedChangeListener((b, checked) -> settings.setSimulateFailure(checked));
        render();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdownNow();
    }

    private String serverInput() {
        return AppSettings.normalize(editServer.getText() == null ? "" : editServer.getText().toString());
    }

    private void render() {
        String user = settings.getUsername();
        if (user != null) {
            textLoginState.setTextColor(ContextCompat.getColor(this, R.color.ok));
            textLoginState.setText("로그인됨: " + user + " @ " + settings.getServerUrl());
            textTokenInfo.setText("Authorization: Token " + TokenStore.mask(settings.getToken()));
            editUsername.setText(user);
        } else {
            textLoginState.setTextColor(ContextCompat.getColor(this, R.color.warn));
            textLoginState.setText("로그인 안 됨 (" + settings.getServerUrl() + ") - 동기화는 가능, 게시는 로그인 필요");
            textTokenInfo.setText("");
        }
    }

    private void login() {
        final String server = serverInput();
        final String username = editUsername.getText() == null ? "" : editUsername.getText().toString().trim();
        final String password = editPassword.getText() == null ? "" : editPassword.getText().toString();
        if (server.isEmpty() || username.isEmpty() || password.isEmpty()) {
            textLoginState.setText("서버 주소, 아이디, 비밀번호를 모두 입력하세요.");
            return;
        }
        btnLogin.setEnabled(false);
        textLoginState.setText("토큰 발급 요청 중... POST " + server + "/api-token-auth/");
        executor.execute(() -> {
            String message;
            boolean ok = false;
            try {
                String token = requestToken(server, username, password);
                settings.saveLogin(server, username, token);
                ok = true;
                message = "로그인 성공";
            } catch (SecurityException e) {
                message = e.getMessage();
            } catch (IOException e) {
                message = "서버에 연결할 수 없습니다: " + e.getMessage();
            } catch (JSONException | GeneralSecurityException e) {
                message = "토큰 처리 오류: " + e.getMessage();
            }
            final String msg = message;
            final boolean success = ok;
            main.post(() -> {
                btnLogin.setEnabled(true);
                editPassword.setText("");
                render();
                Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
                if (!success) {
                    textLoginState.setText(msg);
                }
            });
        });
    }

    /** POST /api-token-auth/ (application/x-www-form-urlencoded) → {"token": "..."} */
    private static String requestToken(String server, String username, String password)
            throws IOException, JSONException {
        HttpURLConnection conn = (HttpURLConnection) new URL(server + "/api-token-auth/").openConnection();
        try {
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
            byte[] body = ("username=" + URLEncoder.encode(username, "UTF-8")
                    + "&password=" + URLEncoder.encode(password, "UTF-8")).getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body);
            }
            int code = conn.getResponseCode();
            if (code == 400) {
                throw new SecurityException("아이디 또는 비밀번호가 올바르지 않습니다.");
            }
            if (code != 200) {
                throw new IOException("HTTP " + code);
            }
            try (InputStream in = conn.getInputStream()) {
                return new JSONObject(new String(ImageCache.readAll(in), StandardCharsets.UTF_8))
                        .getString("token");
            }
        } finally {
            conn.disconnect();
        }
    }
}
