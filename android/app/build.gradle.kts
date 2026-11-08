plugins {
	alias(libs.plugins.android.application)
	alias(libs.plugins.jetbrains.kotlin.android)
}

android {
	namespace = "com.mychatbot.android"
	compileSdk = 36

	defaultConfig {
		applicationId = "com.mychatbot.android"
		minSdk = 33
		targetSdk = 36
		versionCode = 1
		versionName = "1.0"

		ndk {
			abiFilters += listOf("arm64-v8a", "x86_64")
		}
	}

	compileOptions {
		sourceCompatibility = JavaVersion.VERSION_17
		targetCompatibility = JavaVersion.VERSION_17
	}

	kotlin {
		jvmToolchain(17)
	}
}

dependencies {
	implementation(project(":llama"))
	implementation(libs.androidx.activity)
	implementation(libs.androidx.appcompat)
	implementation(libs.androidx.core.ktx)
	implementation(libs.androidx.lifecycle.runtime.ktx)
}
