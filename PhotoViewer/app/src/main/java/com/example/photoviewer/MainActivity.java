package com.example.photoviewer;

import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.AsyncTask;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.TextUtils;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.PickVisualMediaRequest;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.SearchView;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.bottomsheet.BottomSheetBehavior;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;
import com.google.android.material.progressindicator.LinearProgressIndicator;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UnsupportedEncodingException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 강의자료(1) p.18~23 MainActivity
 *  - onClickDownload / CloadImage : 서버의 게시물 목록 동기화 (+ 편의기능 ② ETag·썸네일·캐시)
 *  - onClickUpload / PutPost      : 8. Upload (Post 에 따른 UI 제공) (+ 편의기능 ⑤ 압축·진행률·재시도)
 */
@SuppressWarnings("deprecation") // 강의자료 구조(AsyncTask)를 유지
public class MainActivity extends AppCompatActivity {
    private static final int MY_PERMISSIONS_REQUEST_WRITE_EXTERNAL_STORAGE = 1;

    ImageView imgView;
    TextView textView;
    String site_url = AppSettings.LOCAL_URL;
    JSONObject post_json;
    String imageUrl = null;
    Bitmap bmImg = null;

    CloadImage taskDownload;
    PutPost taskUpload;

    private AppSettings settings;
    private ImageAdapter adapter;
    private SwipeRefreshLayout swipeRefresh;
    private MaterialToolbar toolbar;
    private String searchQuery = "";
    // ---- 공통평가02 편의기능 ① : 감지 필터 ("" = 전체, "edge" = YOLO 감지, "unacked" = 미확인, "label:xxx") ----
    private String filter = "";
    private ChipGroup filterChips;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    // ---- Upload 화면 상태 ----
    private BottomSheetDialog uploadSheet;
    private ImageCompressor.Compressed selectedImage;
    private ImageView uploadPreview;
    private TextView uploadCompressInfo;
    private TextView uploadStatus;
    private TextView uploadLog;
    private LinearProgressIndicator uploadProgress;
    private TextInputEditText editTitle;
    private TextInputEditText editText;
    private TextInputLayout layoutTitle;
    private Button btnSubmit;
    private Button btnPick;

    private final ActivityResultLauncher<PickVisualMediaRequest> pickMedia =
            registerForActivityResult(new ActivityResultContracts.PickVisualMedia(), this::onImagePicked);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_main);
        SystemBars.applyPadding(findViewById(R.id.root));

        settings = new AppSettings(this);
        toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);

        //imgView = (ImageView) findViewById(R.id.imgView);
        textView = (TextView) findViewById(R.id.textView);

        RecyclerView recyclerView = findViewById(R.id.recyclerView);
        recyclerView.setLayoutManager(new LinearLayoutManager(this));
        adapter = new ImageAdapter(new ArrayList<>(), this::openDetail);
        recyclerView.setAdapter(adapter);

        swipeRefresh = findViewById(R.id.swipeRefresh);
        swipeRefresh.setOnRefreshListener(() -> onClickDownload(null));

        filterChips = findViewById(R.id.filterChips);
        renderFilterChips(null);
    }

    // ------------------------------------------------------------------
    // 공통평가02 편의기능 ① : 감지 필터 칩 (서버 /api_root/Post/stats/ 의 클래스 통계로 구성)
    // ------------------------------------------------------------------
    private void renderFilterChips(JSONObject stats) {
        filterChips.removeAllViews();
        addFilterChip("전체", "");
        addFilterChip("YOLO 감지" + (stats != null ? " " + stats.optInt("edge_total") : ""), "edge");
        addFilterChip("미확인" + (stats != null ? " " + stats.optInt("unacked") : ""), "unacked");
        JSONArray byLabel = stats != null ? stats.optJSONArray("by_label") : null;
        if (byLabel != null) {
            for (int i = 0; i < byLabel.length() && i < 10; i++) {
                JSONObject x = byLabel.optJSONObject(i);
                if (x != null) {
                    addFilterChip(x.optString("label") + " " + x.optInt("count"), "label:" + x.optString("label"));
                }
            }
        }
    }

    private void addFilterChip(String text, String value) {
        Chip chip = new Chip(this);
        chip.setText(text);
        chip.setCheckable(true);
        chip.setCheckedIconVisible(false);
        chip.setChecked(value.equals(filter));
        chip.setOnClickListener(v -> {
            filter = value;
            for (int i = 0; i < filterChips.getChildCount(); i++) {
                View child = filterChips.getChildAt(i);
                ((Chip) child).setChecked(child == v);
            }
            onClickDownload(null);
        });
        filterChips.addView(chip);
    }

    /** 검색어 + 감지 필터를 쿼리 문자열로 */
    private String buildQuery() {
        List<String> params = new ArrayList<>();
        try {
            if (!searchQuery.isEmpty()) {
                params.add("search=" + URLEncoder.encode(searchQuery, "UTF-8"));
            }
            if ("edge".equals(filter)) {
                params.add("source=edge");
            } else if ("unacked".equals(filter)) {
                params.add("unacked=1");
            } else if (filter.startsWith("label:")) {
                params.add("label=" + URLEncoder.encode(filter.substring(6), "UTF-8").replace("+", "%20"));
            }
        } catch (UnsupportedEncodingException ignored) {
            // UTF-8 은 항상 지원
        }
        return params.isEmpty() ? "" : "?" + TextUtils.join("&", params);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshSubtitle();
    }

    private void refreshSubtitle() {
        site_url = settings.getServerUrl();
        String user = settings.getUsername();
        toolbar.setSubtitle(site_url + (user != null ? "  ·  " + user : "  ·  로그인 안 됨"));
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdownNow();
    }

    // ------------------------------------------------------------------
    // 메뉴 : 검색 / 로그인·설정 / 캐시 비우기
    // ------------------------------------------------------------------
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu_main, menu);
        MenuItem searchItem = menu.findItem(R.id.action_search);
        SearchView searchView = (SearchView) searchItem.getActionView();
        if (searchView != null) {
            searchView.setQueryHint("제목/내용 검색");
            searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
                @Override
                public boolean onQueryTextSubmit(String query) {
                    searchQuery = query.trim();
                    onClickDownload(null);
                    searchView.clearFocus();
                    return true;
                }

                @Override
                public boolean onQueryTextChange(String newText) {
                    return false;
                }
            });
        }
        searchItem.setOnActionExpandListener(new MenuItem.OnActionExpandListener() {
            @Override
            public boolean onMenuItemActionExpand(MenuItem item) {
                return true;
            }

            @Override
            public boolean onMenuItemActionCollapse(MenuItem item) {
                if (!searchQuery.isEmpty()) {
                    searchQuery = "";
                    onClickDownload(null);
                }
                return true;
            }
        });
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_settings) {
            startActivity(new Intent(this, SettingsActivity.class));
            return true;
        } else if (item.getItemId() == R.id.action_clear_cache) {
            int n = ImageCache.get(this).clear();
            settings.clearSyncCache();
            Toast.makeText(this, "이미지 캐시 " + n + "개 삭제", Toast.LENGTH_SHORT).show();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void openDetail(PostItem post) {
        Intent intent = new Intent(this, DetailActivity.class);
        intent.putExtra(DetailActivity.EXTRA_TITLE, post.title);
        intent.putExtra(DetailActivity.EXTRA_TEXT, post.text);
        intent.putExtra(DetailActivity.EXTRA_META, post.displayDate() + " · " + post.author);
        intent.putExtra(DetailActivity.EXTRA_IMAGE, post.imageUrl);
        intent.putExtra(DetailActivity.EXTRA_ID, post.id);
        intent.putExtra(DetailActivity.EXTRA_IS_DETECTION, post.isDetection());
        intent.putExtra(DetailActivity.EXTRA_ACKED, post.acknowledged);
        intent.putExtra(DetailActivity.EXTRA_SUMMARY, post.detectionSummary());
        intent.putStringArrayListExtra(DetailActivity.EXTRA_DETECTIONS, post.detectionLines);
        startActivity(intent);
    }

    // ==================================================================
    // 동기화 (강의자료 p.20 onClickDownload)
    // ==================================================================
    public void onClickDownload(View v) {
        if (taskDownload != null && taskDownload.getStatus() == AsyncTask.Status.RUNNING) {
            taskDownload.cancel(true);
        }
        site_url = settings.getServerUrl();
        String url = site_url + "/api_root/Post/" + buildQuery();
        swipeRefresh.setRefreshing(true);
        taskDownload = new CloadImage();
        taskDownload.execute(url);
        Toast.makeText(getApplicationContext(), "Download", Toast.LENGTH_SHORT).show();
    }

    /** 동기화 결과 + 성능 측정값 (편의기능 ②) */
    static class SyncResult {
        final List<PostItem> posts = new ArrayList<>();
        long elapsedMs;
        long jsonBytes;
        long imageBytes;
        int cacheHits;
        int downloaded;
        boolean notModified;
        String error;
        JSONObject stats;   // 공통평가02 : 감지 통계
    }

    // 강의자료 p.21~23 CloadImage
    private class CloadImage extends AsyncTask<String, Integer, SyncResult> {
        @Override
        protected SyncResult doInBackground(String... urls) {
            SyncResult result = new SyncResult();
            long start = SystemClock.elapsedRealtime();
            try {
                String apiUrl = urls[0];
                String token = settings.getToken();   // 하드코딩 대신 로그인으로 발급받은 토큰 (편의기능 ④)
                URL urlAPI = new URL(apiUrl);
                HttpURLConnection conn = (HttpURLConnection) urlAPI.openConnection();
                if (token != null) {
                    conn.setRequestProperty("Authorization", "Token " + token);
                }
                String cachedBody = settings.getCachedBody(apiUrl);
                String etag = settings.getEtag(apiUrl);
                if (etag != null && cachedBody != null) {
                    conn.setRequestProperty("If-None-Match", etag);   // 편의기능 ② 조건부 GET
                }
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(5000);

                int responseCode = conn.getResponseCode();
                String strJson;
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    byte[] body;
                    try (InputStream is = conn.getInputStream()) {
                        body = ImageCache.readAll(is);
                    }
                    result.jsonBytes = body.length;
                    strJson = new String(body, StandardCharsets.UTF_8);
                    settings.saveSyncCache(apiUrl, conn.getHeaderField("ETag"), strJson);
                } else if (responseCode == HttpURLConnection.HTTP_NOT_MODIFIED) {
                    result.notModified = true;
                    strJson = cachedBody;
                } else if (responseCode == HttpURLConnection.HTTP_UNAUTHORIZED) {
                    settings.logout();
                    result.error = "인증 토큰이 유효하지 않습니다. 다시 로그인하세요.";
                    return result;
                } else {
                    result.error = "서버 응답 오류: HTTP " + responseCode;
                    return result;
                }
                conn.disconnect();

                JSONArray aryJson = new JSONArray(strJson);
                ImageCache cache = ImageCache.get(MainActivity.this);
                // 배열 내 모든 이미지 다운로드 (목록에는 썸네일)
                for (int i = 0; i < aryJson.length(); i++) {
                    if (isCancelled()) {
                        break;
                    }
                    post_json = (JSONObject) aryJson.get(i);
                    PostItem item = PostItem.fromJson(post_json);
                    imageUrl = item.thumbnailUrl;
                    if (!imageUrl.equals("")) {
                        try {
                            ImageCache.Result img = cache.load(imageUrl, ImageCache.THUMB_MAX);
                            item.bitmap = img.bitmap;
                            if (img.fromCache) {
                                result.cacheHits++;
                            } else {
                                result.downloaded++;
                                result.imageBytes += img.networkBytes;
                            }
                        } catch (IOException e) {
                            e.printStackTrace();   // 이미지 1장 실패가 전체 동기화를 막지 않음
                        }
                    }
                    result.posts.add(item);
                    publishProgress(i + 1, aryJson.length());
                }
                result.stats = fetchStats(token);
            } catch (IOException | JSONException e) {
                e.printStackTrace();
                result.error = e.getClass().getSimpleName() + ": " + e.getMessage();
            } finally {
                result.elapsedMs = SystemClock.elapsedRealtime() - start;
            }
            return result;
        }

        /** 공통평가02 : GET /api_root/Post/stats/ (실패해도 목록 동기화에는 영향 없음) */
        private JSONObject fetchStats(String token) {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(site_url + "/api_root/Post/stats/").openConnection();
                if (token != null) {
                    c.setRequestProperty("Authorization", "Token " + token);
                }
                c.setConnectTimeout(3000);
                c.setReadTimeout(5000);
                if (c.getResponseCode() != HttpURLConnection.HTTP_OK) {
                    return null;
                }
                try (InputStream is = c.getInputStream()) {
                    return new JSONObject(new String(ImageCache.readAll(is), StandardCharsets.UTF_8));
                } finally {
                    c.disconnect();
                }
            } catch (IOException | JSONException e) {
                return null;
            }
        }

        @Override
        protected void onProgressUpdate(Integer... values) {
            textView.setText(String.format(Locale.KOREA, "동기화 중... %d/%d", values[0], values[1]));
        }

        @Override
        protected void onPostExecute(SyncResult r) {
            swipeRefresh.setRefreshing(false);
            if (r.error != null) {
                textView.setTextColor(ContextCompat.getColor(MainActivity.this, R.color.warn));
                textView.setText("동기화 실패 - " + r.error);
                refreshSubtitle();
                return;
            }
            textView.setTextColor(ContextCompat.getColor(MainActivity.this, R.color.muted));
            adapter.setItems(r.posts);
            if (r.stats != null) {
                renderFilterChips(r.stats);
            }
            String searchInfo = searchQuery.isEmpty() ? "" : " ('" + searchQuery + "' 검색)";
            String statsInfo = r.stats == null ? "" : String.format(Locale.KOREA,
                    "\n오늘 감지 %d건 · 미확인 %d건 · 최다 %s",
                    r.stats.optInt("today"), r.stats.optInt("unacked"),
                    r.stats.isNull("top_label") ? "-" : r.stats.optString("top_label"));
            if (r.posts.isEmpty()) {
                textView.setText("불러올 이미지가 없습니다." + searchInfo + statsInfo);
                return;
            }
            textView.setText(String.format(Locale.KOREA,
                    "이미지 로드 성공! %d건%s · %dms\n%s · 받은 데이터 %s (JSON %s + 이미지 %d장 %s) · 캐시 %d/%d%s",
                    r.posts.size(), searchInfo, r.elapsedMs,
                    r.notModified ? "304 Not Modified" : "200 OK",
                    Formats.bytes(r.jsonBytes + r.imageBytes), Formats.bytes(r.jsonBytes),
                    r.downloaded, Formats.bytes(r.imageBytes), r.cacheHits, r.posts.size(), statsInfo));
        }
    }

    // ==================================================================
    // 8. Upload (Post 에 따른 UI 제공)  - 강의자료 p.19 onClickUpload / PutPost
    // ==================================================================
    public void onClickUpload(View v) {
        if (!settings.isLoggedIn()) {
            Toast.makeText(this, "게시하려면 먼저 로그인하세요.", Toast.LENGTH_LONG).show();
            startActivity(new Intent(this, SettingsActivity.class));
            return;
        }
        showUploadSheet();
        Toast.makeText(getApplicationContext(), "Upload", Toast.LENGTH_SHORT).show();
    }

    private void showUploadSheet() {
        uploadSheet = new BottomSheetDialog(this);
        View sheet = getLayoutInflater().inflate(R.layout.dialog_upload, null);
        uploadSheet.setContentView(sheet);
        uploadSheet.getBehavior().setState(BottomSheetBehavior.STATE_EXPANDED);
        uploadSheet.getBehavior().setSkipCollapsed(true);

        ((TextView) sheet.findViewById(R.id.uploadServer)).setText(
                "POST " + settings.getServerUrl() + "/api_root/Post/  ·  " + settings.getUsername());
        uploadPreview = sheet.findViewById(R.id.uploadPreview);
        uploadCompressInfo = sheet.findViewById(R.id.uploadCompressInfo);
        uploadStatus = sheet.findViewById(R.id.uploadStatus);
        uploadLog = sheet.findViewById(R.id.uploadLog);
        uploadProgress = sheet.findViewById(R.id.uploadProgress);
        editTitle = sheet.findViewById(R.id.editTitle);
        editText = sheet.findViewById(R.id.editText);
        layoutTitle = sheet.findViewById(R.id.layoutTitle);
        btnSubmit = sheet.findViewById(R.id.btnSubmit);
        btnPick = sheet.findViewById(R.id.btnPick);
        selectedImage = null;

        View.OnClickListener pick = view -> pickMedia.launch(new PickVisualMediaRequest.Builder()
                .setMediaType(ActivityResultContracts.PickVisualMedia.ImageOnly.INSTANCE)
                .build());
        btnPick.setOnClickListener(pick);
        uploadPreview.setOnClickListener(pick);
        btnSubmit.setOnClickListener(view -> submitPost());
        uploadSheet.setOnDismissListener(d -> {
            if (taskUpload != null && taskUpload.getStatus() == AsyncTask.Status.RUNNING) {
                taskUpload.cancel(true);
            }
        });
        uploadSheet.show();
    }

    private void onImagePicked(Uri uri) {
        if (uri == null || uploadSheet == null) {
            return;
        }
        uploadCompressInfo.setText("이미지 최적화 중...");
        executor.execute(() -> {
            try {
                ImageCompressor.Compressed c = ImageCompressor.compress(this, uri);
                main.post(() -> {
                    selectedImage = c;
                    uploadPreview.setImageBitmap(c.preview);
                    uploadCompressInfo.setText(c.describe());
                    btnPick.setText("다른 사진 선택");
                });
            } catch (IOException | RuntimeException e) {
                main.post(() -> uploadCompressInfo.setText("이미지를 읽을 수 없습니다: " + e.getMessage()));
            }
        });
    }

    private void submitPost() {
        String title = editTitle.getText() == null ? "" : editTitle.getText().toString().trim();
        String text = editText.getText() == null ? "" : editText.getText().toString().trim();
        if (selectedImage == null) {
            uploadStatus.setText("사진을 먼저 선택하세요.");
            return;
        }
        if (TextUtils.isEmpty(title)) {
            layoutTitle.setError("제목을 입력하세요.");
            return;
        }
        layoutTitle.setError(null);
        btnSubmit.setEnabled(false);
        btnPick.setEnabled(false);
        uploadLog.setText("");
        uploadProgress.setVisibility(View.VISIBLE);
        uploadProgress.setProgressCompat(0, false);

        taskUpload = new PutPost(settings.getServerUrl(), settings.getToken(), title, text,
                selectedImage.jpeg, settings.isSimulateFailure());
        taskUpload.execute();
    }

    private void appendLog(String line) {
        CharSequence prev = uploadLog.getText();
        uploadLog.setText(prev.length() == 0 ? line : prev + "\n" + line);
    }

    /** PutPost 의 결과 */
    static class UploadResult {
        boolean success;
        int status;
        int attempts;
        long elapsedMs;
        String message;
        String createdTitle;
    }

    // 강의자료 p.19 : PutPost (multipart : Text + Image)
    private class PutPost extends AsyncTask<Void, Object, UploadResult> {
        static final int MAX_ATTEMPTS = 3;
        private final String server;
        private final String token;
        private final String title;
        private final String text;
        private final byte[] jpeg;
        private final boolean simulateFirstFailure;

        PutPost(String server, String token, String title, String text, byte[] jpeg, boolean simulate) {
            this.server = server;
            this.token = token;
            this.title = title;
            this.text = text;
            this.jpeg = jpeg;
            this.simulateFirstFailure = simulate;
        }

        @Override
        protected UploadResult doInBackground(Void... voids) {
            UploadResult r = new UploadResult();
            long start = SystemClock.elapsedRealtime();
            long delayMs = 1000;
            for (int attempt = 1; attempt <= MAX_ATTEMPTS && !isCancelled(); attempt++) {
                r.attempts = attempt;
                publishProgress("log", "#" + attempt + " POST 전송 시작");
                try {
                    if (simulateFirstFailure && attempt == 1) {
                        publishProgress("progress", 35, (long) jpeg.length);
                        throw new IOException("시뮬레이션: 전송 중 네트워크 연결 끊김");
                    }
                    int code = send(r);
                    r.status = code;
                    if (code == HttpURLConnection.HTTP_CREATED) {
                        r.success = true;
                        break;
                    }
                    if (code >= 500) {
                        throw new IOException("서버 오류 HTTP " + code);
                    }
                    break; // 4xx 는 재시도해도 같은 결과 → 중단
                } catch (IOException e) {
                    r.message = e.getMessage();
                    if (attempt == MAX_ATTEMPTS) {
                        publishProgress("log", "#" + attempt + " 실패: " + e.getMessage() + " → 재시도 중단");
                        break;
                    }
                    publishProgress("retry", attempt, delayMs, e.getMessage());
                    SystemClock.sleep(delayMs);
                    delayMs *= 2; // 지수 백오프 1s → 2s
                }
            }
            r.elapsedMs = SystemClock.elapsedRealtime() - start;
            return r;
        }

        private int send(UploadResult r) throws IOException {
            String boundary = "----PhotoViewer" + System.currentTimeMillis();
            SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US);
            String now = iso.format(new Date());
            String fileName = "photoviewer_" + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
                    .format(new Date()) + ".jpg";

            StringBuilder head = new StringBuilder();
            appendField(head, boundary, "title", title);
            appendField(head, boundary, "text", text);
            appendField(head, boundary, "created_date", now);
            appendField(head, boundary, "published_date", now);
            head.append("--").append(boundary).append("\r\n")
                    .append("Content-Disposition: form-data; name=\"image\"; filename=\"")
                    .append(fileName).append("\"\r\n")
                    .append("Content-Type: image/jpeg\r\n\r\n");
            byte[] headBytes = head.toString().getBytes(StandardCharsets.UTF_8);
            byte[] tailBytes = ("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8);
            long total = headBytes.length + jpeg.length + tailBytes.length;

            HttpURLConnection conn = (HttpURLConnection) new URL(server + "/api_root/Post/").openConnection();
            try {
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(15000);
                conn.setFixedLengthStreamingMode(total);   // 진행률 계산 + 메모리 절약
                conn.setRequestProperty("Authorization", "Token " + token);
                conn.setRequestProperty("Accept", "application/json");
                conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);

                long sent = 0;
                try (OutputStream out = conn.getOutputStream()) {
                    out.write(headBytes);
                    sent += headBytes.length;
                    int chunk = 8 * 1024;
                    int lastPercent = -1;
                    for (int off = 0; off < jpeg.length; off += chunk) {
                        if (isCancelled()) {
                            throw new IOException("사용자 취소");
                        }
                        int len = Math.min(chunk, jpeg.length - off);
                        out.write(jpeg, off, len);
                        sent += len;
                        int percent = (int) (sent * 100 / total);
                        if (percent != lastPercent) {
                            lastPercent = percent;
                            publishProgress("progress", percent, total);
                        }
                    }
                    out.write(tailBytes);
                }
                publishProgress("progress", 100, total);

                int code = conn.getResponseCode();
                InputStream in = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
                String body = in == null ? "" : new String(ImageCache.readAll(in), StandardCharsets.UTF_8);
                if (code == HttpURLConnection.HTTP_CREATED) {
                    try {
                        r.createdTitle = new JSONObject(body).optString("title");
                    } catch (JSONException ignored) {
                        r.createdTitle = title;
                    }
                } else {
                    r.message = body.length() > 300 ? body.substring(0, 300) : body;
                }
                publishProgress("log", "#" + r.attempts + " 응답 HTTP " + code);
                return code;
            } finally {
                conn.disconnect();
            }
        }

        private void appendField(StringBuilder sb, String boundary, String name, String value) {
            sb.append("--").append(boundary).append("\r\n")
                    .append("Content-Disposition: form-data; name=\"").append(name).append("\"\r\n\r\n")
                    .append(value).append("\r\n");
        }

        @Override
        protected void onProgressUpdate(Object... values) {
            if (uploadSheet == null) {
                return;
            }
            String kind = (String) values[0];
            if ("progress".equals(kind)) {
                int percent = (Integer) values[1];
                long total = (Long) values[2];
                uploadProgress.setProgressCompat(percent, true);
                uploadStatus.setTextColor(ContextCompat.getColor(MainActivity.this, R.color.muted));
                uploadStatus.setText(String.format(Locale.KOREA, "업로드 중 %d%%  (%s / %s)",
                        percent, Formats.bytes(total * percent / 100), Formats.bytes(total)));
            } else if ("retry".equals(kind)) {
                int attempt = (Integer) values[1];
                long delay = (Long) values[2];
                uploadStatus.setTextColor(ContextCompat.getColor(MainActivity.this, R.color.warn));
                uploadStatus.setText(String.format(Locale.KOREA, "전송 실패 → %.0f초 후 자동 재시도 (%d/%d)",
                        delay / 1000.0, attempt + 1, MAX_ATTEMPTS));
                appendLog("#" + attempt + " 실패: " + values[3]);
                appendLog("   " + (delay / 1000) + "초 대기 후 재시도");
                uploadProgress.setProgressCompat(0, false);
            } else {
                appendLog((String) values[1]);
            }
        }

        @Override
        protected void onPostExecute(UploadResult r) {
            if (uploadSheet == null) {
                return;
            }
            btnPick.setEnabled(true);
            if (r.success) {
                uploadStatus.setTextColor(ContextCompat.getColor(MainActivity.this, R.color.ok));
                uploadStatus.setText(String.format(Locale.KOREA,
                        "게시 완료 (HTTP 201 Created) · '%s' · 시도 %d회 · %.1f초",
                        r.createdTitle, r.attempts, r.elapsedMs / 1000.0));
                btnSubmit.setText("닫기");
                btnSubmit.setEnabled(true);
                btnSubmit.setOnClickListener(v -> uploadSheet.dismiss());
                onClickDownload(null);   // 게시 직후 목록 자동 동기화
            } else {
                uploadStatus.setTextColor(ContextCompat.getColor(MainActivity.this, R.color.warn));
                String msg = r.status == HttpURLConnection.HTTP_UNAUTHORIZED
                        ? "인증 실패(401) - 다시 로그인하세요."
                        : "게시 실패" + (r.status > 0 ? " (HTTP " + r.status + ")" : "") + " - " + r.message;
                uploadStatus.setText(msg);
                btnSubmit.setText("다시 시도");
                btnSubmit.setEnabled(true);
            }
        }
    }
}
