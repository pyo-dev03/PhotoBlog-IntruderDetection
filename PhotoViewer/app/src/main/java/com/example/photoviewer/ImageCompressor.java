package com.example.photoviewer;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.net.Uri;
import android.provider.OpenableColumns;

import androidx.exifinterface.media.ExifInterface;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

/**
 * 편의기능 ⑤ : 업로드 전 이미지 최적화.
 *  - 긴 변 1600px 로 축소 (inSampleSize + 정확한 스케일)
 *  - EXIF Orientation 을 픽셀에 반영 (세로 사진이 눕지 않도록)
 *  - JPEG 85% 재압축 → 전송량/업로드 시간 감소
 */
public final class ImageCompressor {
    public static final int MAX_DIM = 1600;
    public static final int QUALITY = 85;

    private ImageCompressor() {
    }

    public static final class Compressed {
        public final byte[] jpeg;
        public final Bitmap preview;
        public final long originalBytes;
        public final int originalWidth;
        public final int originalHeight;
        public final int width;
        public final int height;
        public final int rotation;

        Compressed(byte[] jpeg, Bitmap preview, long originalBytes, int ow, int oh, int rotation) {
            this.jpeg = jpeg;
            this.preview = preview;
            this.originalBytes = originalBytes;
            this.originalWidth = ow;
            this.originalHeight = oh;
            this.width = preview.getWidth();
            this.height = preview.getHeight();
            this.rotation = rotation;
        }

        public int savedPercent() {
            if (originalBytes <= 0) {
                return 0;
            }
            return (int) Math.round(100.0 * (originalBytes - jpeg.length) / originalBytes);
        }

        public String describe() {
            return String.format(Locale.KOREA, "원본 %s (%d×%d) → 전송 %s (%d×%d)%s · %d%% 감소",
                    Formats.bytes(originalBytes), originalWidth, originalHeight,
                    Formats.bytes(jpeg.length), width, height,
                    rotation != 0 ? " · EXIF 회전 " + rotation + "° 보정" : "",
                    Math.max(0, savedPercent()));
        }
    }

    public static Compressed compress(Context context, Uri uri) throws IOException {
        ContentResolver cr = context.getContentResolver();

        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream in = cr.openInputStream(uri)) {
            BitmapFactory.decodeStream(in, null, bounds);
        }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            throw new IOException("이미지를 읽을 수 없습니다");
        }

        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = ImageCache.sampleSize(bounds.outWidth, bounds.outHeight, MAX_DIM);
        Bitmap bitmap;
        try (InputStream in = cr.openInputStream(uri)) {
            bitmap = BitmapFactory.decodeStream(in, null, opts);
        }
        if (bitmap == null) {
            throw new IOException("이미지 디코딩 실패");
        }

        float scale = Math.min(1f, MAX_DIM / (float) Math.max(bitmap.getWidth(), bitmap.getHeight()));
        Matrix matrix = new Matrix();
        if (scale < 1f) {
            matrix.postScale(scale, scale);
        }
        int rotation = applyExif(cr, uri, matrix);
        if (!matrix.isIdentity()) {
            Bitmap transformed = Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(),
                    matrix, true);
            if (transformed != bitmap) {
                bitmap.recycle();
            }
            bitmap = transformed;
        }

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.JPEG, QUALITY, out);
        return new Compressed(out.toByteArray(), bitmap, originalSize(cr, uri),
                bounds.outWidth, bounds.outHeight, rotation);
    }

    private static int applyExif(ContentResolver cr, Uri uri, Matrix matrix) {
        int orientation;
        try (InputStream in = cr.openInputStream(uri)) {
            if (in == null) {
                return 0;
            }
            orientation = new ExifInterface(in).getAttributeInt(
                    ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL);
        } catch (IOException e) {
            return 0;
        }
        switch (orientation) {
            case ExifInterface.ORIENTATION_ROTATE_90:
                matrix.postRotate(90);
                return 90;
            case ExifInterface.ORIENTATION_ROTATE_180:
                matrix.postRotate(180);
                return 180;
            case ExifInterface.ORIENTATION_ROTATE_270:
                matrix.postRotate(270);
                return 270;
            case ExifInterface.ORIENTATION_FLIP_HORIZONTAL:
                matrix.postScale(-1, 1);
                return 0;
            case ExifInterface.ORIENTATION_FLIP_VERTICAL:
                matrix.postScale(1, -1);
                return 0;
            case ExifInterface.ORIENTATION_TRANSPOSE:
                matrix.postRotate(90);
                matrix.postScale(-1, 1);
                return 90;
            case ExifInterface.ORIENTATION_TRANSVERSE:
                matrix.postRotate(270);
                matrix.postScale(-1, 1);
                return 270;
            default:
                return 0;
        }
    }

    private static long originalSize(ContentResolver cr, Uri uri) {
        try (Cursor c = cr.query(uri, new String[]{OpenableColumns.SIZE}, null, null, null)) {
            if (c != null && c.moveToFirst() && !c.isNull(0)) {
                return c.getLong(0);
            }
        } catch (RuntimeException ignored) {
            // 일부 provider 는 SIZE 컬럼을 제공하지 않음 → 스트림으로 계산
        }
        long total = 0;
        try (InputStream in = cr.openInputStream(uri)) {
            if (in != null) {
                byte[] buf = new byte[16 * 1024];
                int n;
                while ((n = in.read(buf)) != -1) {
                    total += n;
                }
            }
        } catch (IOException ignored) {
            // 크기를 모르면 0
        }
        return total;
    }
}
