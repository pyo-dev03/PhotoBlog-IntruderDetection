package com.example.photoviewer;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.graphics.drawable.Drawable;
import android.util.AttributeSet;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;

import androidx.annotation.NonNull;
import androidx.appcompat.widget.AppCompatImageView;

/** 상세 화면용 : 두 손가락 확대/축소, 드래그 이동, 더블탭 확대 */
public class ZoomImageView extends AppCompatImageView {
    private static final float MAX_SCALE = 5f;

    private final Matrix base = new Matrix();
    private final Matrix user = new Matrix();
    private final Matrix drawMatrix = new Matrix();
    private float scale = 1f;
    private final ScaleGestureDetector scaleDetector;
    private final GestureDetector gestureDetector;

    public ZoomImageView(Context context) {
        this(context, null);
    }

    public ZoomImageView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setScaleType(ScaleType.MATRIX);
        scaleDetector = new ScaleGestureDetector(context,
                new ScaleGestureDetector.SimpleOnScaleGestureListener() {
                    @Override
                    public boolean onScale(@NonNull ScaleGestureDetector d) {
                        float next = Math.max(1f, Math.min(MAX_SCALE, scale * d.getScaleFactor()));
                        float factor = next / scale;
                        scale = next;
                        user.postScale(factor, factor, d.getFocusX(), d.getFocusY());
                        if (scale == 1f) {
                            user.reset();
                        }
                        apply();
                        return true;
                    }
                });
        gestureDetector = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public boolean onDown(@NonNull MotionEvent e) {
                return true;
            }

            @Override
            public boolean onScroll(MotionEvent e1, @NonNull MotionEvent e2, float dx, float dy) {
                if (scale > 1f) {
                    user.postTranslate(-dx, -dy);
                    apply();
                }
                return true;
            }

            @Override
            public boolean onDoubleTap(@NonNull MotionEvent e) {
                if (scale > 1f) {
                    user.reset();
                    scale = 1f;
                } else {
                    scale = 2.5f;
                    user.postScale(scale, scale, e.getX(), e.getY());
                }
                apply();
                return true;
            }
        });
    }

    @Override
    public void setImageBitmap(Bitmap bm) {
        super.setImageBitmap(bm);
        fitCenter();
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        fitCenter();
    }

    private void fitCenter() {
        Drawable d = getDrawable();
        if (d == null || getWidth() == 0 || getHeight() == 0) {
            return;
        }
        float dw = d.getIntrinsicWidth();
        float dh = d.getIntrinsicHeight();
        float s = Math.min(getWidth() / dw, getHeight() / dh);
        base.setScale(s, s);
        base.postTranslate((getWidth() - dw * s) / 2f, (getHeight() - dh * s) / 2f);
        user.reset();
        scale = 1f;
        apply();
    }

    private void apply() {
        drawMatrix.set(base);
        drawMatrix.postConcat(user);
        setImageMatrix(drawMatrix);
    }

    @SuppressLint("ClickableViewAccessibility")
    @Override
    public boolean onTouchEvent(MotionEvent event) {
        scaleDetector.onTouchEvent(event);
        gestureDetector.onTouchEvent(event);
        if (scale > 1f && getParent() != null) {
            getParent().requestDisallowInterceptTouchEvent(true);
        }
        return true;
    }
}
