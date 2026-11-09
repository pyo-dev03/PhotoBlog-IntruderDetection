package com.example.photoviewer;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.method.ScrollingMovementMethod;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.appbar.MaterialToolbar;

import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 게시물 상세 : 원본 이미지는 이 화면에서만 내려받는다 (목록은 썸네일) + 핀치 줌 */
public class DetailActivity extends AppCompatActivity {
    public static final String EXTRA_TITLE = "title";
    public static final String EXTRA_TEXT = "text";
    public static final String EXTRA_META = "meta";
    public static final String EXTRA_IMAGE = "image";
    // 공통평가02 : YOLO 감지 정보
    public static final String EXTRA_ID = "id";
    public static final String EXTRA_IS_DETECTION = "is_detection";
    public static final String EXTRA_ACKED = "acked";
    public static final String EXTRA_SUMMARY = "summary";
    public static final String EXTRA_DETECTIONS = "detections";

    private boolean acked;
    private Button ackButton;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_detail);
        SystemBars.applyPadding(findViewById(R.id.root));

        MaterialToolbar toolbar = findViewById(R.id.toolbar);
        toolbar.setTitle(getIntent().getStringExtra(EXTRA_TITLE));
        toolbar.setNavigationIcon(R.drawable.ic_arrow_back);
        toolbar.setNavigationOnClickListener(v -> finish());

        ((TextView) findViewById(R.id.detailMeta)).setText(getIntent().getStringExtra(EXTRA_META));
        TextView body = findViewById(R.id.detailText);
        body.setText(getIntent().getStringExtra(EXTRA_TEXT));
        body.setMovementMethod(new ScrollingMovementMethod());

        setupDetection();

        ZoomImageView image = findViewById(R.id.detailImage);
        ProgressBar progress = findViewById(R.id.detailProgress);
        TextView info = findViewById(R.id.detailInfo);
        String url = getIntent().getStringExtra(EXTRA_IMAGE);

        executor.execute(() -> {
            long start = SystemClock.elapsedRealtime();
            try {
                ImageCache.Result r = ImageCache.get(this).load(url, ImageCache.ORIGINAL_MAX);
                long ms = SystemClock.elapsedRealtime() - start;
                main.post(() -> {
                    progress.setVisibility(View.GONE);
                    image.setImageBitmap(r.bitmap);
                    info.setText(String.format(Locale.KOREA, "원본 %d×%d · %s · %dms  (두 손가락 확대, 더블탭 확대/복귀)",
                            r.bitmap.getWidth(), r.bitmap.getHeight(),
                            r.fromCache ? "캐시" : "다운로드 " + Formats.bytes(r.networkBytes), ms));
                });
            } catch (IOException | RuntimeException e) {
                main.post(() -> {
                    progress.setVisibility(View.GONE);
                    info.setText("원본 이미지를 불러오지 못했습니다: " + e.getMessage());
                });
            }
        });
    }

    /** 공통평가02 : 검출 목록 표시 + [확인 처리] 버튼 → POST /api_root/Post/<id>/ack/ */
    private void setupDetection() {
        if (!getIntent().getBooleanExtra(EXTRA_IS_DETECTION, false)) {
            return;
        }
        ArrayList<String> lines = getIntent().getStringArrayListExtra(EXTRA_DETECTIONS);
        TextView dets = findViewById(R.id.detailDetections);
        StringBuilder sb = new StringBuilder(getIntent().getStringExtra(EXTRA_SUMMARY));
        if (lines != null) {
            for (String line : lines) {
                sb.append("\n  • ").append(line);
            }
        }
        dets.setText(sb.toString());
        dets.setVisibility(View.VISIBLE);

        acked = getIntent().getBooleanExtra(EXTRA_ACKED, false);
        ackButton = findViewById(R.id.detailAck);
        ackButton.setVisibility(View.VISIBLE);
        renderAck();
        ackButton.setOnClickListener(v -> sendAck(!acked));
    }

    private void renderAck() {
        ackButton.setText(acked ? "✔ 확인됨 (눌러서 확인 취소)" : "감지 확인 처리");
    }

    private void sendAck(boolean value) {
        AppSettings settings = new AppSettings(this);
        String token = settings.getToken();
        if (token == null) {
            Toast.makeText(this, "확인 처리하려면 먼저 로그인하세요.", Toast.LENGTH_LONG).show();
            return;
        }
        int id = getIntent().getIntExtra(EXTRA_ID, -1);
        String server = settings.getServerUrl();
        ackButton.setEnabled(false);
        executor.execute(() -> {
            int code;
            try {
                HttpURLConnection conn = (HttpURLConnection) new URL(server + "/api_root/Post/" + id + "/ack/").openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(5000);
                conn.setRequestProperty("Authorization", "Token " + token);
                conn.setRequestProperty("Content-Type", "application/json");
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(("{\"acknowledged\": " + value + "}").getBytes(StandardCharsets.UTF_8));
                }
                code = conn.getResponseCode();
                conn.disconnect();
            } catch (IOException e) {
                code = -1;
            }
            final int result = code;
            main.post(() -> {
                ackButton.setEnabled(true);
                if (result == HttpURLConnection.HTTP_OK) {
                    acked = value;
                    renderAck();
                    Toast.makeText(this, acked ? "확인 처리됨" : "확인 취소됨", Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(this, result == 403 ? "작성자(Edge 계정) 또는 관리자만 확인할 수 있습니다."
                            : "확인 처리 실패 (HTTP " + result + ")", Toast.LENGTH_LONG).show();
                }
            });
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdownNow();
    }
}
