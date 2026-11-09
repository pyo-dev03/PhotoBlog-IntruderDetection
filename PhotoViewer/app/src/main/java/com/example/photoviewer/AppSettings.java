package com.example.photoviewer;

import android.content.Context;
import android.content.SharedPreferences;

import java.security.GeneralSecurityException;

/**
 * 편의기능 ④ : 서버 주소 / 로그인 토큰 / 동기화 캐시(ETag) 저장소.
 * 토큰은 평문이 아니라 Android Keystore 로 암호화(TokenStore)해 저장한다.
 */
public class AppSettings {
    public static final String LOCAL_URL = "http://10.0.2.2:8000";
    public static final String CLOUD_URL = "https://vyjsjs.pythonanywhere.com";

    private static final String PREFS = "photoviewer";
    private static final String KEY_SERVER = "server_url";
    private static final String KEY_TOKEN = "token_enc";
    private static final String KEY_TOKEN_SERVER = "token_server";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_SIMULATE = "simulate_failure";

    private final SharedPreferences prefs;

    public AppSettings(Context context) {
        prefs = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** "vyjsjs.pythonanywhere.com/" → "http://vyjsjs.pythonanywhere.com" */
    public static String normalize(String url) {
        String u = url == null ? "" : url.trim();
        while (u.endsWith("/")) {
            u = u.substring(0, u.length() - 1);
        }
        if (!u.isEmpty() && !u.startsWith("http://") && !u.startsWith("https://")) {
            u = "http://" + u;
        }
        return u;
    }

    public String getServerUrl() {
        return prefs.getString(KEY_SERVER, LOCAL_URL);
    }

    public void setServerUrl(String url) {
        prefs.edit().putString(KEY_SERVER, normalize(url)).apply();
    }

    /** 현재 서버에 대해 발급받은 토큰 (서버가 바뀌면 null → 다시 로그인) */
    public String getToken() {
        String server = prefs.getString(KEY_TOKEN_SERVER, null);
        String enc = prefs.getString(KEY_TOKEN, null);
        if (server == null || enc == null || !server.equals(getServerUrl())) {
            return null;
        }
        try {
            return TokenStore.decrypt(enc);
        } catch (GeneralSecurityException | IllegalArgumentException e) {
            return null;
        }
    }

    public boolean isLoggedIn() {
        return getToken() != null;
    }

    public String getUsername() {
        return isLoggedIn() ? prefs.getString(KEY_USERNAME, null) : null;
    }

    public void saveLogin(String server, String username, String token) throws GeneralSecurityException {
        prefs.edit()
                .putString(KEY_SERVER, normalize(server))
                .putString(KEY_TOKEN_SERVER, normalize(server))
                .putString(KEY_USERNAME, username)
                .putString(KEY_TOKEN, TokenStore.encrypt(token))
                .apply();
    }

    public void logout() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_TOKEN_SERVER).remove(KEY_USERNAME).apply();
    }

    public boolean isSimulateFailure() {
        return prefs.getBoolean(KEY_SIMULATE, false);
    }

    public void setSimulateFailure(boolean on) {
        prefs.edit().putBoolean(KEY_SIMULATE, on).apply();
    }

    // ---- 편의기능 ② : 동기화 응답 캐시 (ETag + JSON) ----
    public String getEtag(String url) {
        return prefs.getString("etag:" + url, null);
    }

    public String getCachedBody(String url) {
        return prefs.getString("body:" + url, null);
    }

    public void saveSyncCache(String url, String etag, String body) {
        SharedPreferences.Editor e = prefs.edit();
        if (etag == null) {
            e.remove("etag:" + url).remove("body:" + url);
        } else {
            e.putString("etag:" + url, etag).putString("body:" + url, body);
        }
        e.apply();
    }

    public void clearSyncCache() {
        SharedPreferences.Editor e = prefs.edit();
        for (String key : prefs.getAll().keySet()) {
            if (key.startsWith("etag:") || key.startsWith("body:")) {
                e.remove(key);
            }
        }
        e.apply();
    }
}
