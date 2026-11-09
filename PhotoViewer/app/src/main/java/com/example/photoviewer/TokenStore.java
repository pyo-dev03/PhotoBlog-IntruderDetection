package com.example.photoviewer;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * 편의기능 ④ : API 토큰 암호화 저장.
 * 강의 예제처럼 토큰을 코드에 하드코딩하지 않고, 로그인으로 발급받은 토큰을
 * Android Keystore 의 AES-256/GCM 키로 암호화해 SharedPreferences 에 보관한다.
 */
final class TokenStore {
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "photoviewer_api_token";
    private static final String TRANSFORM = "AES/GCM/NoPadding";

    private TokenStore() {
    }

    private static SecretKey key() throws GeneralSecurityException {
        try {
            KeyStore ks = KeyStore.getInstance(KEYSTORE);
            ks.load(null);
            KeyStore.Entry entry = ks.getEntry(ALIAS, null);
            if (entry instanceof KeyStore.SecretKeyEntry) {
                return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
            }
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            return generator.generateKey();
        } catch (IOException e) {
            throw new GeneralSecurityException(e);
        }
    }

    static String encrypt(String plain) throws GeneralSecurityException {
        Cipher cipher = Cipher.getInstance(TRANSFORM);
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] cipherText = cipher.doFinal(plain.getBytes(StandardCharsets.UTF_8));
        return Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + ":"
                + Base64.encodeToString(cipherText, Base64.NO_WRAP);
    }

    static String decrypt(String stored) throws GeneralSecurityException {
        String[] parts = stored.split(":", 2);
        if (parts.length != 2) {
            throw new GeneralSecurityException("invalid token format");
        }
        Cipher cipher = Cipher.getInstance(TRANSFORM);
        cipher.init(Cipher.DECRYPT_MODE, key(),
                new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }

    /** 화면 표시용 : 앞 6자리만 보여준다 */
    static String mask(String token) {
        if (token == null || token.length() < 8) {
            return "(없음)";
        }
        return token.substring(0, 6) + "••••••••••••" + " (" + token.length() + "자, Keystore 암호화 저장)";
    }
}
