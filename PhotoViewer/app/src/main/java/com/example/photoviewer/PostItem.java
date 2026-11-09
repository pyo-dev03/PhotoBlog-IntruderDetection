package com.example.photoviewer;

import android.graphics.Bitmap;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** GET /api_root/Post/ 응답의 게시물 1건 */
public class PostItem {
    public int id;
    public String title;
    public String text;
    public String author;
    public String publishedDate;
    public String imageUrl;
    public String thumbnailUrl;
    public Bitmap bitmap;

    // ---- 공통평가02 : YOLOv5 Edge Client 침입 감지 정보 ----
    public String source = "manual";
    public String device = "";
    public boolean acknowledged;
    public double maxConfidence = -1;
    public final List<String> labels = new ArrayList<>();
    /** "person 91% [10,20,110,220]" 형태의 검출 목록 (상세 화면 표시용) */
    public final ArrayList<String> detectionLines = new ArrayList<>();

    public static PostItem fromJson(JSONObject json) {
        PostItem item = new PostItem();
        item.id = json.optInt("id", -1);
        item.title = json.optString("title", "");
        item.text = json.optString("text", "");
        item.author = json.optString("author_name", "user " + json.optInt("author"));
        item.publishedDate = json.isNull("published_date") ? "" : json.optString("published_date", "");
        item.imageUrl = json.optString("image", "");
        // 편의기능 ② : 서버가 제공하는 썸네일이 있으면 목록에서는 썸네일만 받는다
        String thumb = json.optString("thumbnail", "");
        item.thumbnailUrl = (thumb == null || thumb.isEmpty() || "null".equals(thumb)) ? item.imageUrl : thumb;

        item.source = json.optString("source", "manual");
        item.device = json.isNull("device") ? "" : json.optString("device", "");
        item.acknowledged = json.optBoolean("acknowledged", false);
        item.maxConfidence = json.isNull("max_confidence") ? -1 : json.optDouble("max_confidence", -1);
        JSONArray labels = json.optJSONArray("labels");
        if (labels != null) {
            for (int i = 0; i < labels.length(); i++) {
                item.labels.add(labels.optString(i));
            }
        }
        JSONArray dets = json.optJSONArray("detections");
        if (dets != null) {
            for (int i = 0; i < dets.length(); i++) {
                JSONObject d = dets.optJSONObject(i);
                if (d == null) {
                    continue;
                }
                StringBuilder line = new StringBuilder(d.optString("label"));
                if (d.has("confidence")) {
                    line.append(String.format(Locale.KOREA, "  %.0f%%", d.optDouble("confidence") * 100));
                }
                JSONArray box = d.optJSONArray("box");
                if (box != null && box.length() == 4) {
                    line.append(String.format(Locale.US, "  [%.0f, %.0f, %.0f, %.0f]",
                            box.optDouble(0), box.optDouble(1), box.optDouble(2), box.optDouble(3)));
                }
                item.detectionLines.add(line.toString());
            }
        }
        return item;
    }

    public boolean isDetection() {
        return "edge".equals(source);
    }

    /** 목록 카드에 표시할 감지 요약 : "● 미확인 · person, cell phone · 최고 91% · cam0" */
    public String detectionSummary() {
        if (!isDetection()) {
            return "";
        }
        StringBuilder sb = new StringBuilder(acknowledged ? "✔ 확인됨" : "● 미확인");
        if (!labels.isEmpty()) {
            sb.append(" · ").append(android.text.TextUtils.join(", ", labels));
        }
        if (maxConfidence >= 0) {
            sb.append(String.format(Locale.KOREA, " · 최고 %.0f%%", maxConfidence * 100));
        }
        if (!device.isEmpty()) {
            sb.append(" · ").append(device);
        }
        return sb.toString();
    }

    /** "2026-10-14T12:03:55.12+09:00" → "2026-10-14 12:03" */
    public String displayDate() {
        if (publishedDate == null || publishedDate.length() < 16) {
            return publishedDate == null ? "" : publishedDate;
        }
        return publishedDate.substring(0, 16).replace('T', ' ');
    }
}
