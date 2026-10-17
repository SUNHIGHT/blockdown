# Platform setup for the `health` package (verified against health 13.3.2)

Minimums: **Android minSdk 26**, **iOS 15.0**, Dart 3.13 / Flutter 3.47.

## Android

1. `android/app/build.gradle(.kts)`: `minSdk = 26`.

2. `MainActivity` must extend `FlutterFragmentActivity` (Health Connect permission dialog):

   ```kotlin
   package com.example.health_app

   import io.flutter.embedding.android.FlutterFragmentActivity

   class MainActivity : FlutterFragmentActivity()
   ```

3. `android/app/src/main/AndroidManifest.xml` (inside `<manifest>`):

   ```xml
   <uses-permission android:name="android.permission.ACTIVITY_RECOGNITION"/>
   <uses-permission android:name="android.permission.health.READ_STEPS"/>
   <uses-permission android:name="android.permission.health.READ_SLEEP"/>

   <queries>
     <package android:name="com.google.android.apps.healthdata" />
     <intent>
       <action android:name="androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE" />
     </intent>
   </queries>
   ```

   Inside `<activity android:name=".MainActivity" ...>` add:

   ```xml
   <intent-filter>
     <action android:name="androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE" />
   </intent-filter>
   ```

   and, as a sibling of `<activity>`, the privacy-policy hook Health Connect requires:

   ```xml
   <activity-alias
       android:name="ViewPermissionUsageActivity"
       android:exported="true"
       android:targetActivity=".MainActivity"
       android:permission="android.permission.START_VIEW_PERMISSION_USAGE">
     <intent-filter>
       <action android:name="android.intent.action.VIEW_PERMISSION_USAGE" />
       <category android:name="android.intent.category.HEALTH_PERMISSIONS" />
     </intent-filter>
   </activity-alias>
   ```

4. Android 13 and older need the **Health Connect app** from Google Play (Android 14+ has it built in);
   `PluginHealthSource.authorize()` opens the Play Store page when it is missing.
5. Health Connect only returns the **last 30 days** after the permission is granted. That is enough for the
   daily sync in this project.
6. Wearables only appear in Health Connect if the watch/ring app writes to it (Fitbit, Samsung Health, Oura,
   Garmin Connect, ... do; check your device's app settings). Sleep from several apps overlaps;
   `summarizeSleep` merges overlaps so minutes are not double-counted.

## iOS

1. `ios/Runner/Info.plist`:

   ```xml
   <key>NSHealthShareUsageDescription</key>
   <string>睡眠と歩数を読み取り、日々の記録に反映します。</string>
   <key>NSHealthUpdateUsageDescription</key>
   <string>睡眠と歩数を読み取り、日々の記録に反映します。</string>
   ```

2. Xcode: Runner target -> Signing & Capabilities -> **+ Capability -> HealthKit**.
3. `ios/Podfile`: `platform :ios, '15.0'`.
4. HealthKit never tells an app whether *read* access was denied (privacy by design), so a denied user simply
   sees empty data. The UI should say "no sleep data found" rather than "permission denied" on iOS.

## Reading the data

* Sleep: Android returns `SLEEP_SESSION` (+ stage samples); iOS returns `SLEEP_IN_BED` and `SLEEP_ASLEEP` /
  stage samples. `PluginHealthSource` asks for whichever of those the platform supports and
  `summarizeSleep` produces one night per wake-up day.
* Steps: `getTotalStepsInInterval` (HealthKit/Health Connect de-duplicate overlapping sources for you).
