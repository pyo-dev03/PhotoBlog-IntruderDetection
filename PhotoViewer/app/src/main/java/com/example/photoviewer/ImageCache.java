package com.example.photoviewer;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.util.LruCache;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * 편의기능 ② : 2단계 이미지 캐시 (메모리 LruCache + 디스크 cacheDir).
 * 같은 URL 의 이미지는 다시 내려받지 않으므로 재동기화 시 네트워크 사용량이 거의 0 이 된다.
 * (서버는 이미지가 바뀌면 파일명이 바뀌므로 URL 을 캐시 키로 써도 안전하다)
 */
public final class ImageCache {
    public static final int THUMB_MAX = 720;
    public static final int ORIGINAL_MAX = 2048;

    private static ImageCache instance;

    private final LruCache<String, Bitmap> memory;
    private final File dir;

    public static final class Result {
        public final Bitmap bitmap;
        public final long networkBytes;
        public final boolean fromCache;

        Result(Bitmap bitmap, long networkBytes, boolean fromCache) {
            this.bitmap = bitmap;
            this.networkBytes = networkBytes;
            this.fromCache = fromCache;
        }
    }

    public static synchronized ImageCache get(Context context) {
        if (instance == null) {
            instance = new ImageCache(context.getApplicationContext());
        }
        return instance;
    }

    private ImageCache(Context context) {
        int maxKb = (int) (Runtime.getRuntime().maxMemory() / 1024 / 8);
        memory = new LruCache<String, Bitmap>(maxKb) {
            @Override
            protected int sizeOf(String key, Bitmap value) {
                return value.getByteCount() / 1024;
            }
        };
        dir = new File(context.getCacheDir(), "images");
        //noinspection ResultOfMethodCallIgnored
        dir.mkdirs();
    }

    public Result load(String url, int maxDim) throws IOException {
        String memKey = maxDim + "|" + url;
        Bitmap hit = memory.get(memKey);
        if (hit != null) {
            return new Result(hit, 0, true);
        }
        File file = new File(dir, sha1(url) + ".img");
        if (file.exists()) {
            Bitmap fromDisk = decodeFile(file, maxDim);
            if (fromDisk != null) {
                memory.put(memKey, fromDisk);
                return new Result(fromDisk, 0, true);
            }
        }

        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(10000);
        try {
            int code = conn.getResponseCode();
            if (code != HttpURLConnection.HTTP_OK) {
                throw new IOException("image HTTP " + code);
            }
            byte[] data;
            try (InputStream in = conn.getInputStream()) {
                data = readAll(in);
            }
            File tmp = new File(dir, file.getName() + ".tmp");
            try (FileOutputStream out = new FileOutputStream(tmp)) {
                out.write(data);
            }
            if (!tmp.renameTo(file)) {
                //noinspection ResultOfMethodCallIgnored
                tmp.delete();
            }
            Bitmap bitmap = decodeBytes(data, maxDim);
            if (bitmap == null) {
                throw new IOException("decode failed: " + url);
            }
            memory.put(memKey, bitmap);
            return new Result(bitmap, data.length, false);
        } finally {
            conn.disconnect();
        }
    }

    public int clear() {
        memory.evictAll();
        int n = 0;
        File[] files = dir.listFiles();
        if (files != null) {
            for (File f : files) {
                if (f.delete()) {
                    n++;
                }
            }
        }
        return n;
    }

    // ---- helpers ----
    static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[16 * 1024];
        int n;
        while ((n = in.read(buf)) != -1) {
            out.write(buf, 0, n);
        }
        return out.toByteArray();
    }

    static int sampleSize(int w, int h, int maxDim) {
        int sample = 1;
        while (w / (sample * 2) >= maxDim || h / (sample * 2) >= maxDim) {
            sample *= 2;
        }
        return sample;
    }

    private static Bitmap decodeBytes(byte[] data, int maxDim) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, maxDim);
        return BitmapFactory.decodeByteArray(data, 0, data.length, opts);
    }

    private static Bitmap decodeFile(File file, int maxDim) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getPath(), bounds);
        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, maxDim);
        return BitmapFactory.decodeFile(file.getPath(), opts);
    }

    private static String sha1(String s) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-1").digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : d) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            return Integer.toHexString(s.hashCode());
        }
    }
}
