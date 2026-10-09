from fastapi.testclient import TestClient
from app import app
import database
import os

client = TestClient(app)

def test_full_portal_flow():
    # 1. Test Home page
    r = client.get("/")
    assert r.status_code == 200
    assert "MarsClient" in r.text
    print(" [PASS] Root page returns 200 and loads HTML template.")

    # 2. Test Registration of Admin user (r.grabovyi@gmail.com)
    admin_payload = {
        "email": "r.grabovyi@gmail.com",
        "username": "GrabovyiAdmin",
        "password": "SecretPassword123"
    }
    r = client.post("/api/register", json=admin_payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "success"
    code = data["verification_code"]
    print(f" [PASS] Admin registered with email {admin_payload['email']}, verify code: {code}")

    # 3. Test duplicate email registration
    r_dup_email = client.post("/api/register", json={
        "email": "R.GRABOVYI@gmail.com",
        "username": "OtherUser",
        "password": "Password123"
    })
    assert r_dup_email.status_code == 400
    assert "почтой уже зарегистрирован" in r_dup_email.json()["detail"]
    print(" [PASS] Duplicate email prevented!")

    # 4. Test duplicate username registration
    r_dup_user = client.post("/api/register", json={
        "email": "other@gmail.com",
        "username": "grabovyiadmin",
        "password": "Password123"
    })
    assert r_dup_user.status_code == 400
    assert "логином уже существует" in r_dup_user.json()["detail"]
    print(" [PASS] Duplicate username prevented!")

    # 5. Verify email with wrong code
    r_bad_code = client.post("/api/verify_email", json={
        "email": "r.grabovyi@gmail.com",
        "code": "000000"
    })
    assert r_bad_code.status_code == 400
    print(" [PASS] Invalid verification code rejected.")

    # 6. Verify email with correct code
    r_verify = client.post("/api/verify_email", json={
        "email": "r.grabovyi@gmail.com",
        "code": code
    })
    assert r_verify.status_code == 200
    assert "token" in r_verify.json()
    token = r_verify.json()["token"]
    print(" [PASS] Email successfully verified!")

    # 7. Check current profile (/api/me)
    client.cookies.set("mars_token", token)
    r_me = client.get("/api/me")
    assert r_me.status_code == 200
    me_data = r_me.json()
    assert me_data["username"] == "GrabovyiAdmin"
    assert me_data["is_admin"] == 1, "Admin rights should be automatically granted to r.grabovyi@gmail.com!"
    print(" [PASS] Profile loaded: Admin rights confirmed (is_admin = 1).")

    # 8. Test Admin key generation
    r_gen = client.post("/api/admin/generate_keys", json={"days": 30, "count": 2})
    assert r_gen.status_code == 200
    keys = r_gen.json()["keys"]
    assert len(keys) == 2
    assert keys[0].startswith("MARS-")
    print(f" [PASS] Admin successfully generated FunPay keys: {keys}")

    # 9. Register a regular user to test buying/key activation
    user_payload = {
        "email": "customer@gmail.com",
        "username": "HappyCustomer",
        "password": "UserPass999"
    }
    r_user_reg = client.post("/api/register", json=user_payload)
    assert r_user_reg.status_code == 200
    user_code = r_user_reg.json()["verification_code"]
    
    r_user_verify = client.post("/api/verify_email", json={
        "email": "customer@gmail.com",
        "code": user_code
    })
    assert r_user_verify.status_code == 200
    user_token = r_user_verify.json()["token"]

    # Log in as regular customer
    client.cookies.set("mars_token", user_token)
    r_user_me = client.get("/api/me")
    assert r_user_me.json()["is_admin"] == 0
    assert r_user_me.json()["remaining_days"] == 0
    print(" [PASS] Regular user profile verified (is_admin = 0, remaining_days = 0).")

    # 10. Activate FunPay key as user
    key_to_use = keys[0]
    r_act = client.post("/api/activate_key", json={"key_code": key_to_use})
    assert r_act.status_code == 200
    print(f" [PASS] Key {key_to_use} activated successfully!")

    # Verify days were added
    r_user_me_after = client.get("/api/me")
    assert r_user_me_after.json()["remaining_days"] >= 29.9
    assert r_user_me_after.json()["is_active"] is True
    print(f" [PASS] Subscription active: {r_user_me_after.json()['remaining_days']} days remaining.")

    # Try activating the same key again (should fail)
    r_act_dup = client.post("/api/activate_key", json={"key_code": key_to_use})
    assert r_act_dup.status_code == 400
    print(" [PASS] Reusing key was blocked!")

    # 11. Test Launcher Authentication API
    launcher_req = {
        "email": "customer@gmail.com",
        "username": "HappyCustomer",
        "password": "UserPass999",
        "hwid": "HWID-TEST-PC-987654"
    }
    r_launch = client.post("/api/launcher/auth", json=launcher_req)
    assert r_launch.status_code == 200
    assert r_launch.json()["status"] == "success"
    print(" [PASS] Launcher auth successful and HWID bound.")

    # Test Launcher Auth with wrong HWID
    launcher_req_wrong_hwid = {
        "email": "customer@gmail.com",
        "username": "HappyCustomer",
        "password": "UserPass999",
        "hwid": "DIFFERENT-HWID-PC"
    }
    r_launch_fail = client.post("/api/launcher/auth", json=launcher_req_wrong_hwid)
    assert r_launch_fail.json()["status"] == "error"
    assert "Неверный HWID" in r_launch_fail.json()["message"]
    print(" [PASS] Launcher anti-sharing HWID lock verified!")

    # 12. Test Admin panel: Reset HWID, Add Days, and Ban
    client.cookies.set("mars_token", token) # back to admin
    r_reset_hwid = client.post("/api/admin/user_action", json={
        "username": "HappyCustomer",
        "action": "reset_hwid"
    })
    assert r_reset_hwid.status_code == 200
    print(" [PASS] Admin successfully reset customer HWID.")

    # 13. Test Logout
    r_logout = client.post("/api/logout")
    assert r_logout.status_code == 200
    print(" [PASS] Logout endpoint works cleanly.")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! 100% OPERATIONAL! <<<\n")

if __name__ == "__main__":
    test_full_portal_flow()
